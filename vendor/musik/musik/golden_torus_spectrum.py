"""High-density, audio-driven circular spectrum teeth for Golden Torus v2.2.

Only 48 independent measurements are available at default settings. Each
measurement is represented by three sharply tapered, closely packed teeth;
these are *not* 144 independent frequency bins.
"""
from __future__ import annotations

import numpy as np

SPECTRUM_BANDS = 48
TEETH_PER_BAND = 3
TEETH_COUNT = SPECTRUM_BANDS * TEETH_PER_BAND
PROFILE_SAMPLES = 4608  # 32 texture samples per tooth; vertex mesh has 16


def prepare_bands(levels, count: int = SPECTRUM_BANDS) -> np.ndarray:
	"""Convert MusiK's dB-compressed FFT levels to positive radial heights."""
	values = np.asarray(levels, dtype=np.float32).reshape(-1)
	if values.size == 0:
		return np.zeros(count, dtype=np.float32)
	values = np.clip(np.nan_to_num(values, nan=0.0, posinf=1.0, neginf=0.0), 0.0, 1.0)
	if values.size != count:
		x_old = (np.arange(values.size) + 0.5) / values.size
		x_new = (np.arange(count) + 0.5) / count
		values = np.interp(x_new, x_old, values, left=values[0], right=values[-1]).astype(np.float32)

	# The source signal is already logarithmic and range-compressed. A small
	# noise gate avoids dancing at true silence; gamma lifts quiet instruments.
	# Do not mix neighboring bands: the spatial tooth taper does that job.
	active = np.maximum(values - 0.025, 0.0)
	active = np.clip(active * 1.45, 0.0, 1.0)
	return np.ascontiguousarray(active ** 0.72, dtype=np.float32)


def ring_profile(bands, samples: int = PROFILE_SAMPLES) -> np.ndarray:
	"""Build pointed peaks with flat valleys, periodically tiled around the ring.

	Peak centres are at (i + 1/2) / TEETH_COUNT; all cell boundaries are
	zero. This guarantees a seamless join EVEN when lowest/highest frequency
	bands have different amplitudes. The 1D profile is passed to OpenGL as
	a one-row single-component floating-point texture.
	"""
	b = np.asarray(bands, dtype=np.float32).reshape(-1)
	if b.size != SPECTRUM_BANDS:
		raise ValueError(f"Expected {SPECTRUM_BANDS} bands, got {b.size}")
	if samples < TEETH_COUNT * 8:
		raise ValueError("At least 8 texture samples per tooth are needed")

	# Frequency content at each tooth centre: 3 peaks interpolate between
	# adjacent real FFT bands, not extra invented frequencies.
	tooth_id = np.arange(TEETH_COUNT)
	band_pos = (tooth_id + 0.5) / TEETH_PER_BAND - 0.5
	left = np.floor(band_pos).astype(np.intp)
	mix = band_pos - left
	tooth_heights = b[left % b.size] * (1 - mix) + b[(left + 1) % b.size] * mix

	phase = (np.arange(samples, dtype=np.float32) + 0.5) / samples * TEETH_COUNT
	index = np.floor(phase).astype(np.intp)
	distance = np.abs(phase - index - 0.5) * 2.0
	# Narrow, sharp tooth: centre=1, nearly all of each cell's edges=0.
	# Exponent < 1 keeps an angular point at the tip (not a round hump).
	width = 0.90
	tooth_shape = np.maximum(1.0 - distance / width, 0.0) ** 1.10
	profile = tooth_heights[index % TEETH_COUNT] * tooth_shape
	return np.ascontiguousarray(profile, dtype=np.float32)
