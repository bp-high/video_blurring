FROM python:3.11-slim-bookworm

RUN pip install --no-cache-dir \
    opencv-python-headless==5.0.0.93 \
    numpy==2.4.6 \
    imageio-ffmpeg==0.6.0

# imageio-ffmpeg ships a static ffmpeg; expose it on PATH for the agent,
# the oracle, and the verifier alike
RUN ln -s "$(python3 -c 'import imageio_ffmpeg; print(imageio_ffmpeg.get_ffmpeg_exe())')" \
    /usr/local/bin/ffmpeg

WORKDIR /app
COPY seed/ /app/
RUN mkdir -p /app/output
