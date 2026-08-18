#!/bin/sh
set -eu

archive=/input/opencv-5.0.0.tar.gz
patch_file=/input-wrapper/opencv-5.0.0-r08-no-msvc-pdb.patch
source_root=/usr/src/opencv-5.0.0
build_root=/usr/src/opencv-build
install_root=/work/stage/opt/project-mirror-opencv5
wrapper_source=/usr/src/project-mirror-opencv-wrapper
wrapper_build=/usr/src/project-mirror-opencv-wrapper-build

test "$(sha256sum "$archive" | cut -d ' ' -f 1)" = \
  b0528f5a1d379d59d4701cb28c36e22214cc51cf64594e5b56f2d3e6c0233095
test "$(sha256sum "$patch_file" | cut -d ' ' -f 1)" = \
  e42a75d9b42584197ba444eda90b001da1120e72e68327e573dd77d8fc802da3

mkdir -p "$build_root" "$wrapper_build"
tar -xzf "$archive" -C /usr/src
cp -a /input-wrapper "$wrapper_source"
patch -d "$source_root" -p1 --forward < "$patch_file"

cmake -S "$source_root" -B "$build_root" -G Ninja \
  -DCMAKE_BUILD_TYPE=Release \
  -DCMAKE_INSTALL_PREFIX=/opt/project-mirror-opencv5 \
  -DCMAKE_BUILD_RPATH_USE_ORIGIN=ON \
  -DCMAKE_INSTALL_RPATH='$ORIGIN' \
  -DCMAKE_INSTALL_RPATH_USE_LINK_PATH=OFF \
  -DBUILD_INFO_SKIP_TIMESTAMP=ON \
  -DBUILD_LIST=core,imgproc \
  -DBUILD_SHARED_LIBS=ON \
  -DBUILD_TESTS=OFF \
  -DBUILD_PERF_TESTS=OFF \
  -DBUILD_EXAMPLES=OFF \
  -DBUILD_opencv_apps=OFF \
  -DBUILD_opencv_python3=OFF \
  -DBUILD_JAVA=OFF \
  -DBUILD_PROTOBUF=OFF \
  -DBUILD_ZLIB=ON \
  -DWITH_1394=OFF \
  -DWITH_ADE=OFF \
  -DWITH_CUDA=OFF \
  -DWITH_EIGEN=OFF \
  -DWITH_FFMPEG=OFF \
  -DWITH_GDAL=OFF \
  -DWITH_GSTREAMER=OFF \
  -DWITH_GTK=OFF \
  -DWITH_IPP=OFF \
  -DWITH_ITT=OFF \
  -DWITH_JASPER=OFF \
  -DWITH_JPEG=OFF \
  -DWITH_LAPACK=OFF \
  -DWITH_OPENCL=OFF \
  -DWITH_OPENEXR=OFF \
  -DWITH_OPENGL=OFF \
  -DWITH_OPENJPEG=OFF \
  -DWITH_OPENMP=OFF \
  -DWITH_PNG=OFF \
  -DWITH_PROTOBUF=OFF \
  -DWITH_QT=OFF \
  -DWITH_TBB=OFF \
  -DWITH_TIFF=OFF \
  -DWITH_V4L=OFF \
  -DWITH_VA=OFF \
  -DWITH_VTK=OFF \
  -DWITH_WEBP=OFF \
  -DCV_ENABLE_INTRINSICS=OFF \
  -DCPU_DISPATCH= \
  -DENABLE_LTO=OFF \
  -DOPENCV_ENABLE_NONFREE=OFF \
  -DOPENCV_GENERATE_PKGCONFIG=OFF \
  2>&1 | tee /work/opencv-configure.log

cmake --build "$build_root" --parallel 4 2>&1 | tee /work/opencv-build.log
DESTDIR=/work/stage cmake --install "$build_root" 2>&1 | tee /work/opencv-install.log

cmake -S "$wrapper_source" -B "$wrapper_build" -G Ninja \
  -DCMAKE_BUILD_TYPE=Release \
  -DCMAKE_INSTALL_PREFIX=/opt/project-mirror-opencv5 \
  -DCMAKE_BUILD_RPATH_USE_ORIGIN=ON \
  -DCMAKE_INSTALL_RPATH='$ORIGIN' \
  -DCMAKE_INSTALL_RPATH_USE_LINK_PATH=OFF \
  -DOpenCV_DIR="$install_root/lib/cmake/opencv5" \
  2>&1 | tee /work/wrapper-configure.log
cmake --build "$wrapper_build" --parallel 4 2>&1 | tee /work/wrapper-build.log
DESTDIR=/work/stage cmake --install "$wrapper_build" 2>&1 | tee /work/wrapper-install.log

python3 /input-wrapper/run_minimal_remap_poc.py \
  --library "$install_root/lib/libmirror_opencv_remap.so" \
  --artifact-dir /work/harness-artifacts \
  --output /work/harness-report.json \
  2>&1 | tee /work/harness.log

cc --version | head -1 > /work/toolchain.txt
ld --version | head -1 >> /work/toolchain.txt
ldd --version | head -1 >> /work/toolchain.txt
find "$install_root/lib" -maxdepth 1 -type f -print0 \
  | sort -z \
  | xargs -0 sha256sum > /work/runtime-sha256.txt
