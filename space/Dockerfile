# NOT USED: the Space is static (scripts/build_static_space.py); a Docker Space for an organisation needs Hugging
# Face's Team plan. Kept in case that changes.
# Andy's TV page on sample data, for judges and visitors: no robot, no camera, no models, no keys.
FROM python:3.12-slim
RUN useradd -m -u 1000 user
WORKDIR /home/user/app
RUN pip install --no-cache-dir pillow==13.0.0
COPY --chown=user . .
USER user
EXPOSE 7860
CMD ["python", "scripts/demo_screen.py", "--public", "--host", "0.0.0.0", "--port", "7860"]
