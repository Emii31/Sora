#include "scyllasband.h"

#include <algorithm>
#include <cmath>
#include <cstdio>
#include <iostream>
#include <memory>
#include <string>
#include <vector>

namespace {
int32_t emit_audio(const ScyllasBandEvent* event, void*) {
    if (event->type != SCYLLASBAND_EVENT_AUDIO) return 0;
    std::vector<unsigned char> bytes;
    bytes.reserve(static_cast<std::size_t>(event->sample_count) * 2);
    for (int64_t index = 0; index < event->sample_count; ++index) {
        const auto pcm = static_cast<uint16_t>(static_cast<int16_t>(
            std::lrint(std::clamp(event->samples[index], -1.0f, 1.0f) * 32767.0f)));
        bytes.push_back(static_cast<unsigned char>(pcm));
        bytes.push_back(static_cast<unsigned char>(pcm >> 8));
    }
    if (std::printf("pcm %d %zu\n", event->sample_rate, bytes.size()) < 0 ||
        std::fwrite(bytes.data(), 1, bytes.size(), stdout) != bytes.size()) return 1;
    return std::fflush(stdout) == 0 ? 0 : 1;
}
}

int main(int argc, char** argv) {
    if (argc != 2) {
        std::fprintf(stderr, "usage: gwen-stream BUNDLE\n");
        return 2;
    }

    const ScyllasBandRuntimeOptions options{argv[1], 4, SCYLLASBAND_ACCELERATOR_CPU};
    ScyllasBandRuntime* raw_runtime = nullptr;
    if (scyllasband_runtime_create(&options, &raw_runtime) != SCYLLASBAND_OK) {
        std::fprintf(stderr, "%s\n", scyllasband_last_error());
        return 1;
    }
    const std::unique_ptr<ScyllasBandRuntime, decltype(&scyllasband_runtime_destroy)>
        runtime(raw_runtime, scyllasband_runtime_destroy);
    if (scyllasband_warmup(runtime.get(), "gwen") != SCYLLASBAND_OK) {
        std::fprintf(stderr, "%s\n", scyllasband_last_error());
        return 1;
    }
    // Exercise a longer continuation before taking interactive requests.
    ScyllasBandRequest preroll{};
    scyllasband_request_init(&preroll);
    preroll.voice_id = "gwen";
    preroll.language = "en_us";
    preroll.text = "I'm here. I'll open the window and move this chair a little closer. "
                   "We can take our time and talk about whatever is on your mind today.";
    const auto discard = [](const ScyllasBandEvent*, void*) -> int32_t { return 0; };
    if (scyllasband_synthesize_stream(runtime.get(), &preroll, discard, nullptr) != SCYLLASBAND_OK) {
        std::fprintf(stderr, "%s\n", scyllasband_last_error());
        return 1;
    }

    std::puts("ready");
    std::fflush(stdout);

    std::string line;
    while (std::getline(std::cin, line)) {
        const auto split = line.find('\t');
        if (line.size() > 4096 || split == std::string::npos || split == line.size() - 1) {
            std::puts("error");
            std::fflush(stdout);
            continue;
        }
        const auto delivery = line.substr(0, split);
        ScyllasBandRequest request{};
        scyllasband_request_init(&request);
        request.voice_id = "gwen";
        request.language = "en_us";
        request.delivery = delivery.c_str();
        request.text = line.c_str() + split + 1;
        const auto status = scyllasband_synthesize_stream(runtime.get(), &request, emit_audio, nullptr);
        if (status != SCYLLASBAND_OK) std::fprintf(stderr, "%s\n", scyllasband_last_error());
        std::puts(status == SCYLLASBAND_OK ? "done" : "error");
        if (std::fflush(stdout) != 0) return 1;
    }
}
