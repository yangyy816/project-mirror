FROM python@sha256:ffb752e139c0a19692a43af8d8523b274222dd68eebad5d583b45c2201c6e30a

ARG SOURCE_DATE_EPOCH=1788130800
ENV DEBIAN_FRONTEND=noninteractive \
    LANG=C.UTF-8 \
    LC_ALL=C.UTF-8 \
    TZ=UTC \
    SOURCE_DATE_EPOCH=${SOURCE_DATE_EPOCH}

COPY debs/ /opt/mirror-cc08/debs/

RUN dpkg --unpack /opt/mirror-cc08/debs/*.deb \
    && dpkg --configure --pending \
    && test -z "$(dpkg --audit)" \
    && rm -rf /var/lib/apt/lists/* /opt/mirror-cc08/debs

COPY bazel-7.4.1-linux-x86_64 /usr/local/bin/bazel
RUN chmod 0755 /usr/local/bin/bazel \
    && test "$(sha256sum /usr/local/bin/bazel | cut -d' ' -f1)" = \
      "c97f02133adce63f0c28678ac1f21d65fa8255c80429b588aeeba8a1fac6202b" \
    && test "$(bazel --version)" = "bazel 7.4.1" \
    && gcc --version \
    && cmake --version \
    && ninja --version

WORKDIR /workspace
