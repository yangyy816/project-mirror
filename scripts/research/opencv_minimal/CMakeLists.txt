cmake_minimum_required(VERSION 3.25)

project(mirror_opencv_remap VERSION 1.0.0 LANGUAGES CXX)

find_package(OpenCV 5.0.0 EXACT REQUIRED COMPONENTS core imgproc)

add_library(mirror_opencv_remap SHARED mirror_opencv_remap.cpp)
target_compile_features(mirror_opencv_remap PRIVATE cxx_std_17)
target_link_libraries(mirror_opencv_remap PRIVATE opencv_core opencv_imgproc)
target_include_directories(mirror_opencv_remap PRIVATE ${OpenCV_INCLUDE_DIRS})
target_compile_definitions(mirror_opencv_remap PRIVATE MIRROR_OPENCV_REMAP_BUILD)

if(MSVC)
  target_compile_options(mirror_opencv_remap PRIVATE /Brepro /EHsc /W4)
  target_link_options(mirror_opencv_remap PRIVATE /Brepro /INCREMENTAL:NO /DEBUG:NONE)
else()
  target_compile_options(
    mirror_opencv_remap
    PRIVATE
      -fvisibility=hidden
      -ffile-prefix-map=${CMAKE_SOURCE_DIR}=.
      -ffile-prefix-map=${CMAKE_BINARY_DIR}=.
      -Wall
      -Wextra
      -Wpedantic
  )
  target_link_options(mirror_opencv_remap PRIVATE -Wl,--build-id=none)
  set_target_properties(
    mirror_opencv_remap
    PROPERTIES BUILD_RPATH "$ORIGIN" INSTALL_RPATH "$ORIGIN"
  )
endif()

set_target_properties(
  mirror_opencv_remap
  PROPERTIES
    CXX_EXTENSIONS OFF
    OUTPUT_NAME mirror_opencv_remap
    POSITION_INDEPENDENT_CODE ON
)

install(TARGETS mirror_opencv_remap RUNTIME DESTINATION bin LIBRARY DESTINATION lib)
