#include <opencv2/core.hpp>
#include <opencv2/imgproc.hpp>

#include <cmath>
#include <cstddef>
#include <cstdint>

#if defined(_WIN32)
#if defined(MIRROR_OPENCV_REMAP_BUILD)
#define MIRROR_EXPORT __declspec(dllexport)
#else
#define MIRROR_EXPORT __declspec(dllimport)
#endif
#else
#define MIRROR_EXPORT __attribute__((visibility("default")))
#endif

namespace {

constexpr std::int32_t kMaxEdge = 4096;

bool valid_map(const float* values, std::int32_t width, std::int32_t height,
               std::ptrdiff_t stride_bytes, float lower, float upper) {
  for (std::int32_t row = 0; row < height; ++row) {
    const auto* row_bytes = reinterpret_cast<const std::uint8_t*>(values) + row * stride_bytes;
    const auto* row_values = reinterpret_cast<const float*>(row_bytes);
    for (std::int32_t column = 0; column < width; ++column) {
      const float value = row_values[column];
      if (!std::isfinite(value) || value < lower || value > upper) {
        return false;
      }
    }
  }
  return true;
}

}  // namespace

extern "C" {

MIRROR_EXPORT const char* mirror_opencv_runtime_version() noexcept { return CV_VERSION; }

MIRROR_EXPORT std::int32_t mirror_opencv_remap_rgb_u8(
    const std::uint8_t* source, std::int32_t width, std::int32_t height,
    std::ptrdiff_t source_stride_bytes, const float* map_x, const float* map_y,
    std::ptrdiff_t map_stride_bytes, std::uint8_t* output,
    std::ptrdiff_t output_stride_bytes) noexcept {
  if (source == nullptr || map_x == nullptr || map_y == nullptr || output == nullptr) {
    return 10;
  }
  if (width <= 0 || height <= 0 || width > kMaxEdge || height > kMaxEdge) {
    return 11;
  }
  const auto minimum_rgb_stride = static_cast<std::ptrdiff_t>(width) * 3;
  const auto minimum_map_stride = static_cast<std::ptrdiff_t>(width) * sizeof(float);
  if (source_stride_bytes < minimum_rgb_stride || output_stride_bytes < minimum_rgb_stride ||
      map_stride_bytes < minimum_map_stride) {
    return 12;
  }
  if (!valid_map(map_x, width, height, map_stride_bytes, 0.0F,
                 static_cast<float>(width - 1)) ||
      !valid_map(map_y, width, height, map_stride_bytes, 0.0F,
                 static_cast<float>(height - 1))) {
    return 13;
  }

  try {
    cv::setNumThreads(1);
    cv::setUseOptimized(false);
    const cv::Mat source_view(height, width, CV_8UC3, const_cast<std::uint8_t*>(source),
                              source_stride_bytes);
    const cv::Mat map_x_view(height, width, CV_32FC1, const_cast<float*>(map_x), map_stride_bytes);
    const cv::Mat map_y_view(height, width, CV_32FC1, const_cast<float*>(map_y), map_stride_bytes);
    cv::Mat output_view(height, width, CV_8UC3, output, output_stride_bytes);
    cv::remap(source_view, output_view, map_x_view, map_y_view, cv::INTER_LINEAR,
              cv::BORDER_REFLECT_101);
    return 0;
  } catch (const cv::Exception&) {
    return 20;
  } catch (...) {
    return 21;
  }
}

}  // extern "C"
