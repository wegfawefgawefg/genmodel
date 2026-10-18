#pragma once

// Sound bank and mixer. Clips are prepared offline (tools/sounds.py); cues layer clips with
// per-trigger variation; the animation's sound and hum tracks say when. Rendering is a pure
// function of time, so live playback, scrubbing and the video export all hear the same thing.

#include "anim.hpp"

#include <cstdint>
#include <string>
#include <vector>

const int sound_rate = 48000;

struct SoundLayer {
    std::vector<int> clips; // one is picked per trigger
    float g0 = 1, g1 = 1;   // gain range
    float p0 = 1, p1 = 1;   // pitch (playback speed) range
    float d0 = 0, d1 = 0;   // delay range, seconds
    bool fixed_pan = false; // otherwise it pans with its trigger
    float pan = 0, spread = 0;
};

struct SoundCue {
    std::string name;
    std::vector<SoundLayer> layers;
};

struct SoundEvent {
    float t;
    int cue;
    float gain, pan;
    uint32_t seed;
};

// a looping cue whose level and pitch follow a driver; phase is integrated at load
struct SoundHum {
    int cue = -1;
    Drive by;
    float gain = 1, p0 = 1, p1 = 1;
    std::vector<double> phase; // seconds into the clip, per anim table step
    double phase_loop = 0;     // phase gained over one loop
};

struct SoundBank {
    std::vector<std::string> clip_names;
    std::vector<std::vector<float>> clips;
    std::vector<SoundCue> cues;
    std::vector<SoundEvent> events; // one loop
    std::vector<SoundHum> hums;
    bool ok = false;
};

// reads the bank's cues and the clips in clip_dir (<sample>.wav)
bool load_sound_bank(const std::string& bank_path, const std::string& clip_dir, SoundBank& out);
// turns the animation's sound and hum tracks into events and hum phase tables
void sound_prepare(SoundBank& bank, const Anim& anim);
// mixes interleaved stereo for absolute time t0 (it loops with the anim), frames samples long
void sound_render(const SoundBank& bank, const Anim& anim, double t0, int frames, float* stereo);
bool write_wav16(const std::string& path, const std::vector<float>& stereo);
