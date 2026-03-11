from fastapi import FastAPI, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
import essentia.standard as es
import numpy as np
import tempfile
import os

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"]
)

@app.post("/analyze")
async def analyze(file: UploadFile = File(...)):
    # Save uploaded file to temp
    with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(file.filename or ".mp3")[1]) as tmp:
        content = await file.read()
        tmp.write(content)
        tmp_path = tmp.name

    try:
        # Load audio with Essentia
        audio = es.MonoLoader(filename=tmp_path, sampleRate=44100)()

        # --- Pitch Analysis ---
        pitch_extractor = es.PredominantPitchMelodia()
        pitch_values, pitch_confidence = pitch_extractor(audio)
        valid_pitches = pitch_values[pitch_values > 0]
        vocal_confidence = float(np.mean(pitch_confidence[pitch_values > 0]) * 100) if len(valid_pitches) > 0 else 0

        # Pitch accuracy = how stable the pitch is (lower std = more accurate)
        if len(valid_pitches) > 1:
            pitch_std = float(np.std(valid_pitches))
            pitch_accuracy = max(0, min(100, 100 - (pitch_std / 5)))
        else:
            pitch_accuracy = 0

        # --- Rhythm / Tempo ---
        rhythm_extractor = es.RhythmExtractor2013(method="multifeature")
        bpm, beats, beats_confidence, _, _ = rhythm_extractor(audio)
        tempo_bpm = float(bpm)

        # Timing accuracy from beat intervals regularity
        if len(beats) > 2:
            intervals = np.diff(beats)
            timing_std = float(np.std(intervals))
            median_interval = float(np.median(intervals))
            timing_accuracy = max(0, min(100, 100 - (timing_std / median_interval * 100))) if median_interval > 0 else 0
        else:
            timing_accuracy = 50

        # --- Energy ---
        energy = es.Energy()(audio)
        rms = es.RMS()(audio)
        energy_score = float(min(10, rms * 100))

        # --- Spectral Brightness ---
        spectrum = es.Spectrum()(audio)
        centroid = es.Centroid(range=22050)(spectrum)
        spectral_brightness = float(min(100, centroid * 100 / 5000))

        # --- Dynamic Range ---
        envelope = es.Envelope()(audio)
        dynamic_range = float(min(100, (np.max(envelope) - np.min(envelope)) * 100))

        # --- Onset Strength ---
        onsets = es.OnsetRate()(audio)
        onset_rate = float(onsets[1]) if len(onsets) > 1 else 0
        onset_strength = float(min(100, onset_rate * 10))

        # --- Overall Score ---
        overall_score = round(
            (
                pitch_accuracy * 0.25
                + timing_accuracy * 0.2
                + vocal_confidence * 0.2
                + spectral_brightness * 0.1
                + energy_score * 10 * 0.1
                + dynamic_range * 0.1
                + onset_strength * 0.05
            ),
            1
        )

        return {
            "pitch_accuracy": round(pitch_accuracy, 1),
            "timing_accuracy": round(timing_accuracy, 1),
            "tempo_bpm": round(tempo_bpm, 1),
            "energy_score": round(energy_score, 1),
            "spectral_brightness": round(spectral_brightness, 1),
            "dynamic_range": round(dynamic_range, 1),
            "onset_strength": round(onset_strength, 1),
            "vocal_confidence": round(vocal_confidence, 1),
            "overall_score": round(overall_score, 1),

            # Legacy fields for backward compatibility
            "rhythm_stability": round(timing_accuracy, 1),
            "tone_quality": round(energy_score * 10, 1),
        }

    finally:
        os.unlink(tmp_path)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))
