#include "sound.hpp"

#include "anim_util.hpp"
#include "sexp_read.hpp"

#include <cmath>
#include <cstdio>
#include <cstring>
#include <fstream>

namespace {

// 16-bit PCM or 32-bit float wav, any channel count, mixed down to mono
bool read_wav(const std::string& path, std::vector<float>& out) {
    std::ifstream f(path, std::ios::binary);
    if (!f) {
        return false;
    }
    std::vector<char> b((std::istreambuf_iterator<char>(f)), std::istreambuf_iterator<char>());
    if (b.size() < 12 || memcmp(b.data(), "RIFF", 4) != 0 || memcmp(b.data() + 8, "WAVE", 4) != 0) {
        return false;
    }
    int format = 0, channels = 1, bits = 16;
    size_t pos = 12;
    while (pos + 8 <= b.size()) {
        uint32_t size;
        memcpy(&size, b.data() + pos + 4, 4);
        const char* body = b.data() + pos + 8;
        if (memcmp(b.data() + pos, "fmt ", 4) == 0) {
            uint16_t v;
            memcpy(&v, body, 2), format = v;
            memcpy(&v, body + 2, 2), channels = v;
            memcpy(&v, body + 14, 2), bits = v;
        } else if (memcmp(b.data() + pos, "data", 4) == 0) {
            size = std::min<uint32_t>(size, (uint32_t)(b.size() - pos - 8));
            size_t frames = size / (bits / 8) / channels;
            out.assign(frames, 0);
            for (size_t i = 0; i < frames; i++) {
                float sum = 0;
                for (int c = 0; c < channels; c++) {
                    size_t at = (i * channels + c) * (bits / 8);
                    if (format == 3 && bits == 32) {
                        float v;
                        memcpy(&v, body + at, 4);
                        sum += v;
                    } else {
                        int16_t v;
                        memcpy(&v, body + at, 2);
                        sum += v / 32768.0f;
                    }
                }
                out[i] = sum / channels;
            }
            return true;
        }
        pos += 8 + size + (size & 1);
    }
    return false;
}

int clip_index(SoundBank& bank, const std::string& name) {
    for (size_t i = 0; i < bank.clip_names.size(); i++) {
        if (bank.clip_names[i] == name) return (int)i;
    }
    return -1;
}

int cue_index(const SoundBank& bank, const std::string& name) {
    for (size_t i = 0; i < bank.cues.size(); i++) {
        if (bank.cues[i].name == name) return (int)i;
    }
    fprintf(stderr, "sound: no cue named %s\n", name.c_str());
    return -1;
}

// (layer sample-or-(pick a b) (gain lo hi) (pitch lo hi) (delay lo hi) (pan p) (spread s))
SoundLayer read_layer(gsexp::Node form, SoundBank& bank) {
    SoundLayer l;
    for (size_t i = 1; i < form.child_count(); i++) {
        gsexp::Node c = form.child_at(i);
        std::string h = head_of(c);
        if (!c.is_list()) {
            int k = clip_index(bank, std::string(c.text()));
            if (k >= 0) l.clips.push_back(k);
        } else if (h == "pick") {
            for (size_t j = 1; j < c.child_count(); j++) {
                int k = clip_index(bank, std::string(c.child_at(j).text()));
                if (k >= 0) l.clips.push_back(k);
            }
        } else if (h == "gain") {
            l.g0 = num(c.child_at(1), 1);
            l.g1 = num(c.child_at(2), l.g0);
        } else if (h == "pitch") {
            l.p0 = num(c.child_at(1), 1);
            l.p1 = num(c.child_at(2), l.p0);
        } else if (h == "delay") {
            l.d0 = num(c.child_at(1), 0);
            l.d1 = num(c.child_at(2), l.d0);
        } else if (h == "pan") {
            l.fixed_pan = true;
            l.pan = num(c.child_at(1), 0);
        } else if (h == "spread") {
            l.spread = num(c.child_at(1), 0);
        }
    }
    return l;
}

float pick_range(float lo, float hi, uint32_t seed, uint32_t salt) { return lo + (hi - lo) * hash01(seed, salt); }

// linear interpolated sample, 0 outside the clip
float tap(const std::vector<float>& clip, double pos) {
    if (pos < 0) return 0;
    size_t i = (size_t)pos;
    if (i + 1 >= clip.size()) return 0;
    float f = (float)(pos - i);
    return clip[i] + (clip[i + 1] - clip[i]) * f;
}

void pan_gains(float pan, float& l, float& r) {
    float a = (std::clamp(pan, -1.0f, 1.0f) + 1) * 0.785398f;
    l = std::cos(a), r = std::sin(a);
}

// one triggered cue, starting from absolute time `at`, into the block [t0, t0 + frames)
void mix_event(const SoundBank& bank, const SoundEvent& e, double at, uint32_t loop, double t0, int frames, float* out) {
    const SoundCue& cue = bank.cues[e.cue];
    for (size_t li = 0; li < cue.layers.size(); li++) {
        const SoundLayer& l = cue.layers[li];
        if (l.clips.empty()) continue;
        uint32_t seed = e.seed * 131u + loop * 7919u + (uint32_t)li * 31u;
        const std::vector<float>& clip = bank.clips[l.clips[(size_t)(hash01(seed, 1) * l.clips.size()) % l.clips.size()]];
        float gain = pick_range(l.g0, l.g1, seed, 2) * e.gain;
        float pitch = pick_range(l.p0, l.p1, seed, 3);
        double start = at + pick_range(l.d0, l.d1, seed, 4);
        float pan = (l.fixed_pan ? l.pan : e.pan) + (hash01(seed, 5) * 2 - 1) * l.spread;
        double dur = clip.size() / (sound_rate * (double)pitch);
        double end = start + dur;
        if (end <= t0 || start >= t0 + frames / (double)sound_rate) continue;
        float gl, gr;
        pan_gains(pan, gl, gr);
        int i0 = std::max(0, (int)std::floor((start - t0) * sound_rate));
        int i1 = std::min(frames, (int)std::ceil((end - t0) * sound_rate));
        for (int i = i0; i < i1; i++) {
            double pos = ((t0 + (double)i / sound_rate) - start) * sound_rate * pitch;
            float v = tap(clip, pos) * gain;
            out[i * 2] += v * gl;
            out[i * 2 + 1] += v * gr;
        }
    }
}

} // namespace

bool load_sound_bank(const std::string& bank_path, const std::string& clip_dir, SoundBank& out) {
    std::string text;
    if (!read_text(bank_path, text)) {
        return false;
    }
    gsexp::ParseResult r = gsexp::parse(text);
    if (!r.ok || r.root_count() == 0) {
        print_diagnostics(bank_path, r);
        return false;
    }
    SoundBank bank;
    // clips first, so cues can name them
    for (gsexp::Node c : r.root(0).children()) {
        if (head_of(c) != "sample") continue;
        std::string name(c.child_at(1).text());
        std::vector<float> clip;
        if (!read_wav(clip_dir + "/" + name + ".wav", clip)) {
            fprintf(stderr, "sound: missing %s/%s.wav (run tools/sounds.py)\n", clip_dir.c_str(), name.c_str());
        }
        bank.clip_names.push_back(name);
        bank.clips.push_back(std::move(clip));
    }
    for (gsexp::Node c : r.root(0).children()) {
        if (head_of(c) != "cue") continue;
        SoundCue cue;
        cue.name = std::string(c.child_at(1).text());
        for (size_t i = 2; i < c.child_count(); i++) {
            if (head_of(c.child_at(i)) == "layer") {
                cue.layers.push_back(read_layer(c.child_at(i), bank));
            }
        }
        bank.cues.push_back(cue);
    }
    bank.ok = true;
    printf("sound %s: %zu clips, %zu cues\n", bank_path.c_str(), bank.clips.size(), bank.cues.size());
    out = std::move(bank);
    return true;
}

void sound_prepare(SoundBank& bank, const Anim& a) {
    bank.events.clear();
    bank.hums.clear();
    for (size_t ti = 0; ti < a.tracks.size(); ti++) {
        const Track& t = a.tracks[ti];
        if (t.kind == TrackKind::sound) {
            int cue = cue_index(bank, t.cue);
            if (cue < 0) continue;
            if (t.at >= 0) {
                bank.events.push_back({t.at, cue, t.gain, t.pan, (uint32_t)ti * 100003u});
                continue;
            }
            for (size_t i = 0; i < a.shots.size(); i++) {
                if ((int)i % t.every != t.offset % t.every) continue;
                bank.events.push_back({a.shots[i], cue, t.gain, t.pan, (uint32_t)i * 977u + (uint32_t)ti * 100003u});
            }
        } else if (t.kind == TrackKind::hum) {
            SoundHum h;
            h.cue = cue_index(bank, t.cue);
            if (h.cue < 0) continue;
            h.by = t.by, h.gain = t.gain, h.p0 = t.pitch_lo, h.p1 = t.pitch_hi;
            // integrate the playback speed so the loop's pitch can slide without clicks
            double phase = 0;
            for (size_t i = 0; i < a.rate_table.size(); i++) {
                h.phase.push_back(phase);
                float d = std::clamp(drive(a, h.by, i * a.table_dt), 0.0f, 1.0f);
                phase += (h.p0 + (h.p1 - h.p0) * d) * a.table_dt;
            }
            h.phase_loop = h.phase.empty() ? 0 : h.phase.back();
            bank.hums.push_back(h);
        }
    }
}

void sound_render(const SoundBank& bank, const Anim& a, double t0, int frames, float* out) {
    std::fill(out, out + frames * 2, 0.0f);
    if (!bank.ok || a.length <= 0) {
        return;
    }
    // triggered cues from this loop and its neighbours (tails cross the seam)
    long loop = (long)std::floor(t0 / a.length);
    for (long k = loop - 1; k <= loop + 1; k++) {
        if (k < 0) continue;
        for (const SoundEvent& e : bank.events) {
            mix_event(bank, e, k * (double)a.length + e.t, (uint32_t)k, t0, frames, out);
        }
    }
    // hums: level follows the driver, phase from the integrated table
    for (const SoundHum& h : bank.hums) {
        const SoundCue& cue = bank.cues[h.cue];
        if (cue.layers.empty() || cue.layers[0].clips.empty()) continue;
        const std::vector<float>& clip = bank.clips[cue.layers[0].clips[0]];
        if (clip.size() < 2) continue;
        float g = cue.layers[0].g0 * h.gain;
        for (int i = 0; i < frames; i++) {
            double t = t0 + (double)i / sound_rate;
            long k = (long)std::floor(t / a.length);
            float tw = (float)(t - k * (double)a.length);
            float level = std::pow(std::clamp(drive(a, h.by, tw), 0.0f, 1.0f), 0.7f) * g;
            if (level < 1e-4f) continue;
            float x = tw / a.table_dt;
            size_t j = std::min((size_t)x, h.phase.size() - 2);
            double ph = h.phase[j] + (h.phase[j + 1] - h.phase[j]) * (x - j) + k * h.phase_loop;
            double pos = std::fmod(ph * sound_rate, (double)(clip.size() - 1));
            float v = tap(clip, pos) * level;
            out[i * 2] += v;
            out[i * 2 + 1] += v;
        }
    }
    // soft saturation: stacked shots bark rather than clip
    for (int i = 0; i < frames * 2; i++) {
        out[i] = std::tanh(out[i] * 1.6f) / std::tanh(1.6f) * 0.84f;
    }
}

bool write_wav16(const std::string& path, const std::vector<float>& stereo) {
    std::ofstream f(path, std::ios::binary);
    if (!f) {
        return false;
    }
    uint32_t data = (uint32_t)(stereo.size() * 2), riff = 36 + data, fmt = 16, rate = sound_rate, bps = rate * 4;
    uint16_t pcm = 1, ch = 2, align = 4, bits = 16;
    f.write("RIFF", 4), f.write((char*)&riff, 4), f.write("WAVEfmt ", 8), f.write((char*)&fmt, 4);
    f.write((char*)&pcm, 2), f.write((char*)&ch, 2), f.write((char*)&rate, 4), f.write((char*)&bps, 4);
    f.write((char*)&align, 2), f.write((char*)&bits, 2), f.write("data", 4), f.write((char*)&data, 4);
    for (float v : stereo) {
        int16_t s = (int16_t)std::lround(std::clamp(v, -1.0f, 1.0f) * 32767.0f);
        f.write((char*)&s, 2);
    }
    return true;
}
