# TestOps, as a container.
#
# The package has no runtime dependencies beyond the standard library, so there is nothing to
# install and no lockfile to drift: the image is the interpreter plus the code plus one store.
#
# The store is baked in on purpose. This deployment exists to be shown to a team, and a
# read-mostly snapshot of one analysed project is more useful than an empty database that needs a
# PAT and a network fetch before the first page renders. Writes made in the container are lost when
# it scales to zero - that is a property of the demo, not of the tool.
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    TESTOPS_DATA=/app/data

WORKDIR /app

COPY testops/ ./testops/
COPY data/testops.db ./data/testops.db
COPY data/blobs/ ./data/blobs/

EXPOSE 8080

# 0.0.0.0 so the platform can reach it; the port is the one Container Apps targets.
CMD ["python", "-m", "testops.cli", "serve", "--host", "0.0.0.0", "--port", "8080"]
