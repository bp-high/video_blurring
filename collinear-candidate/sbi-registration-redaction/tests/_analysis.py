"""State tracking and failure analysis for the redaction verifier.

Turns the per-sample records the grader collects into three things a
reviewer can act on:

  * a PII inventory  - what in this video counts as sensitive, why, and
    when it is on screen (plus what is deliberately NOT sensitive);
  * a state timeline - page by page, which sensitive values are expected
    on screen and what the candidate actually did with each;
  * findings         - one line per defect, naming the item, the failure
    mode, and the times, so a model run can be analysed without
    re-watching the video.
"""


def _runs(times, fps, gap=0.5):
    """Group sample times into contiguous runs. `gap` should exceed the
    spacing of the samples being grouped, so a continuous defect reads as
    one interval instead of a list of isolated instants."""
    out = []
    for t in sorted(times):
        if out and t - out[-1][1] <= gap + 1.0 / fps:
            out[-1][1] = t
        else:
            out.append([t, t])
    return [[round(a, 3), round(b, 3)] for a, b in out]


def _fmt(runs, limit=3):
    """Render runs compactly: a few intervals, then a count."""
    head = ", ".join(f"{a}-{b}s" if b > a else f"{a}s" for a, b in runs[:limit])
    return head + (f" (+{len(runs) - limit} more)" if len(runs) > limit else "")


def build(gt, res, fps, scores):
    redact_meta = {i["id"]: i.get("meta", {}) for i in gt["redact"]}
    windows = {}
    for i in gt["redact"]:
        ts = [s["t"] for s in i["samples"]]
        windows[i["id"]] = _runs(ts, fps, gap=1.0)

    # ---- what counts as PII here, and what deliberately does not ----
    inventory = []
    for i in gt["redact"]:
        m = i.get("meta", {})
        n_hard = sum(1 for s in i["samples"] if s.get("hard"))
        inventory.append(dict(
            id=i["id"], label=m.get("label", i["id"]),
            category=m.get("category", "unclassified"),
            page=m.get("page"), rationale=m.get("why"),
            on_screen=windows[i["id"]],
            samples=len(i["samples"]), hard_samples=n_hard))
    not_pii = []
    for i in gt.get("visible", []):
        m = i.get("meta", {})
        not_pii.append(dict(id=i["id"], label=m.get("label", i["id"]),
                            reason=m.get("reason", "must remain legible"),
                            samples=len(i["samples"])))

    # ---- per-item outcome ----
    per_item = {}
    for iid, (ok, tot) in res["cov"].items():
        leaks = res["leaks"].get(iid, [])
        cov = ok / tot if tot else 0.0
        if cov == 1.0:
            verdict = "redacted"
        elif cov == 0.0:
            verdict = "not_redacted"
        else:
            verdict = "partially_redacted"
        per_item[iid] = dict(
            label=redact_meta.get(iid, {}).get("label", iid),
            coverage=round(cov, 3), samples=tot, leaked=len(leaks),
            leak_runs=_runs(leaks, fps), first_leak=(min(leaks) if leaks else None),
            weak_blur=len(res["weak"].get(iid, [])), verdict=verdict)

    # ---- state timeline: per page, what was expected and what happened ----
    pages = gt.get("pages", [])
    timeline = []
    for pg in pages:
        t1, t2 = pg["t1"], pg["t2"]
        expected, leaked, ok_ids = [], [], []
        for iid, wins in windows.items():
            if any(not (b < t1 or a > t2) for a, b in wins):
                expected.append(iid)
                if per_item.get(iid, {}).get("leaked"):
                    if any(t1 <= t <= t2 for t in res["leaks"].get(iid, [])):
                        leaked.append(iid)
                        continue
                ok_ids.append(iid)
        enc = [k for k, v in res["nbr_bad"].items()
               if any(t1 <= t <= t2 for t in v)]
        obl = [k for k, v in res["vis_bad"].items()
               if any(t1 <= t <= t2 for t in v)]
        timeline.append(dict(
            page=pg["name"], t=[t1, t2],
            pii_expected=sorted(expected), pii_redacted=sorted(ok_ids),
            pii_leaked=sorted(leaked), neighbours_clipped=sorted(enc),
            legible_content_obscured=sorted(obl),
            status=("clean" if not (leaked or enc or obl) else "defect")))

    # ---- findings ----
    findings = []
    for iid, d in sorted(per_item.items(), key=lambda kv: kv[1]["coverage"]):
        if d["verdict"] == "not_redacted":
            findings.append(
                f"MISSED — {d['label']} ({iid}) was never redacted; readable "
                f"across {d['samples']} sampled frames at {_fmt(windows.get(iid, []))}")
        elif d["verdict"] == "partially_redacted":
            findings.append(
                f"PARTIAL — {d['label']} ({iid}) redacted for "
                f"{d['samples'] - d['leaked']}/{d['samples']} samples; still "
                f"readable at {_fmt(d['leak_runs'])}")
        if d["weak_blur"]:
            findings.append(
                f"WEAK — {d['label']} ({iid}) covered on {d['weak_blur']} "
                f"samples by a change too small to be a real obscuring patch")
    vis_meta = {i["id"]: i.get("meta", {}) for i in gt.get("visible", [])}
    nbr_meta = {i["id"]: i.get("meta", {}) for i in gt.get("neighbors", [])}
    for iid, times in sorted(res["vis_bad"].items()):
        findings.append(
            f"OVER-REDACTED — {vis_meta.get(iid, {}).get('label', iid)} ({iid}) "
            f"must stay legible but no longer "
            f"matches at {_fmt(_runs(times, fps, gap=1.2))}")
    for iid, times in sorted(res["nbr_bad"].items()):
        findings.append(
            f"ENCROACHED — a redaction overlapped its neighbouring text "
            f"({iid}) at {_fmt(_runs(times, fps, gap=1.2))}")
    if res["budget_bad"]:
        findings.append(
            f"OVER-BLUR — off-target changed pixels exceeded the frame budget "
            f"on {len(res['budget_bad'])} sampled frames at "
            f"{_fmt(_runs(res['budget_bad'], fps, gap=2.2))}")
    if not findings:
        findings.append("No defects: every sensitive value is covered on every "
                        "sampled frame, nothing that must stay legible was "
                        "touched, and no redaction overlapped its neighbours.")

    return dict(pii_inventory=inventory, not_pii=not_pii, per_item=per_item,
                state_timeline=timeline, findings=findings, scores=scores)


def to_markdown(a, reward):
    L = ["# Redaction analysis", "",
         "## Scores", ""]
    for k in ("overall", "functional_correctness", "constraint_satisfaction",
              "neighbor_legibility", "robustness", "artifact_quality"):
        if reward.get(k) is not None:
            L.append(f"- `{k}`: {reward[k]}")
    L += ["", "## What counts as PII in this video", "",
          "| item | what it is | category | page | on screen | samples (hard) |",
          "|---|---|---|---|---|---|"]
    for i in a["pii_inventory"]:
        L.append(f"| `{i['id']}` | {i['label']} | {i['category']} | "
                 f"{i['page']} | {i['on_screen']} | {i['samples']} "
                 f"({i['hard_samples']}) |")
    if a["not_pii"]:
        L += ["", "## Deliberately NOT redacted (must stay legible)", "",
              "| item | what it is | why it is not redacted |", "|---|---|---|"]
        for i in a["not_pii"]:
            L.append(f"| `{i['id']}` | {i['label']} | {i['reason']} |")
    L += ["", "## What the candidate did", "",
          "| item | verdict | coverage | leaked samples | leak times |",
          "|---|---|---|---|---|"]
    for iid, d in sorted(a["per_item"].items()):
        L.append(f"| `{iid}` | {d['verdict']} | {d['coverage']} | "
                 f"{d['leaked']}/{d['samples']} | {d['leak_runs'] or '-'} |")
    if a["state_timeline"]:
        L += ["", "## State timeline", "",
              "| page | t | PII expected | redacted | leaked | neighbours clipped | legible content obscured | status |",
              "|---|---|---|---|---|---|---|---|"]
        for r in a["state_timeline"]:
            L.append(f"| {r['page']} | {r['t'][0]}–{r['t'][1]} | "
                     f"{len(r['pii_expected'])} | {len(r['pii_redacted'])} | "
                     f"{', '.join(r['pii_leaked']) or '-'} | "
                     f"{', '.join(r['neighbours_clipped']) or '-'} | "
                     f"{', '.join(r['legible_content_obscured']) or '-'} | "
                     f"{r['status']} |")
    L += ["", "## Findings", ""] + [f"- {f}" for f in a["findings"]] + [""]
    return "\n".join(L)
