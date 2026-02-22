"""
Fourier Ptychographic Microscopy (FPM) Reconstruction
======================================================
Algorithm: Iterative phase retrieval using Gerchberg-Saxton style updates.

각 LED 조명 각도로 촬영한 저해상도 이미지들을 합성해
고해상도 복소 이미지를 복원합니다.

Reference:
  Zheng et al., "Wide-field, high-resolution Fourier ptychographic microscopy",
  Nature Photonics, 2013.
"""

import numpy as np
from numpy.fft import fft2, ifft2, fftshift, ifftshift
from dataclasses import dataclass
from typing import Optional
import warnings


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

@dataclass
class FPMConfig:
    """FPM 시스템 파라미터."""
    wavelength: float = 0.6328e-6      # 파장 [m] (He-Ne 레이저 예시)
    NA_obj: float = 0.08               # 대물렌즈 개구수
    pixel_size_camera: float = 6.5e-6  # 카메라 픽셀 크기 [m]
    magnification: float = 4.0         # 배율
    led_pitch: float = 4e-3            # LED 간격 [m]
    led_distance: float = 67e-3        # 샘플~LED 거리 [m]
    upsample_factor: int = 4           # 고해상도 업샘플 배율
    n_iterations: int = 50             # 반복 횟수
    led_grid_size: int = 15            # LED 격자 크기 (led_grid_size x led_grid_size)
    regularization: float = 1e-6       # Tikhonov 정규화 계수

    @property
    def pixel_size_object(self) -> float:
        """물체 평면에서의 유효 픽셀 크기 [m]."""
        return self.pixel_size_camera / self.magnification

    @property
    def k0(self) -> float:
        """파수 [1/m]."""
        return 2 * np.pi / self.wavelength

    @property
    def NA_illumination_max(self) -> float:
        """LED 격자가 커버하는 최대 조명 NA."""
        half = (self.led_grid_size // 2) * self.led_pitch
        return half / np.sqrt(half**2 + self.led_distance**2)


# ---------------------------------------------------------------------------
# LED 배열 좌표 생성
# ---------------------------------------------------------------------------

def compute_led_positions(cfg: FPMConfig) -> tuple[np.ndarray, np.ndarray]:
    """
    LED 격자의 (kx, ky) 주파수 좌표 배열 반환.
    단위: 물체 평면의 공간 주파수 [1/m].
    """
    n = cfg.led_grid_size
    half = n // 2
    idx = np.arange(-half, half + 1) if n % 2 == 1 else np.arange(-half, half)
    gy, gx = np.meshgrid(idx, idx, indexing='ij')  # (n, n)

    # LED 위치 → 조명 각도 → 공간 주파수
    dx = gx * cfg.led_pitch
    dy = gy * cfg.led_pitch
    dist = np.sqrt(dx**2 + dy**2 + cfg.led_distance**2)

    sin_x = dx / dist
    sin_y = dy / dist

    kx = cfg.k0 * sin_x  # [rad/m]
    ky = cfg.k0 * sin_y

    return kx.ravel(), ky.ravel()


# ---------------------------------------------------------------------------
# 저역통과 마스크 (대물렌즈 pupil)
# ---------------------------------------------------------------------------

def make_pupil_mask(cfg: FPMConfig, hr_shape: tuple[int, int]) -> np.ndarray:
    """
    고해상도 주파수 공간에서의 대물렌즈 pupil 마스크 (원형).
    """
    Ny, Nx = hr_shape
    # 공간 주파수 축 [1/m]  (fftshift 기준)
    fs_y = np.fft.fftfreq(Ny, d=cfg.pixel_size_object / cfg.upsample_factor)
    fs_x = np.fft.fftfreq(Nx, d=cfg.pixel_size_object / cfg.upsample_factor)
    FY, FX = np.meshgrid(fftshift(fs_y), fftshift(fs_x), indexing='ij')

    k_cutoff = cfg.NA_obj / cfg.wavelength   # 최대 공간 주파수 [1/m]
    mask = (FX**2 + FY**2) <= k_cutoff**2
    return mask.astype(float)


# ---------------------------------------------------------------------------
# 주파수 공간에서 저해상도 윈도우 중심 인덱스 계산
# ---------------------------------------------------------------------------

def freq_to_pixel(k: float, size: int, pixel_size: float, upsample: int) -> int:
    """
    공간 주파수 k [rad/m] → 고해상도 배열(fftshift 기준)에서의 인덱스.
    """
    effective_pixel = pixel_size / upsample
    # fftshift 기준: 배열 중심이 DC
    center = size // 2
    idx = center + int(np.round(k / (2 * np.pi) * size * effective_pixel))
    return idx


# ---------------------------------------------------------------------------
# 저해상도 패치 추출 / 삽입 유틸리티
# ---------------------------------------------------------------------------

def extract_patch(arr: np.ndarray, cy: int, cx: int, patch_h: int, patch_w: int) -> np.ndarray:
    """
    arr (fftshift 기준)에서 (cy, cx) 중심의 (patch_h x patch_w) 패치 추출.
    경계를 벗어나는 영역은 0으로 패딩.
    항상 (patch_h, patch_w) 크기의 배열을 반환.
    """
    Ny, Nx = arr.shape
    patch = np.zeros((patch_h, patch_w), dtype=arr.dtype)

    # 소스 배열에서 읽을 범위
    ys = cy - patch_h // 2
    xs = cx - patch_w // 2
    ye = ys + patch_h
    xe = xs + patch_w

    # 유효 소스 범위
    src_ys = max(0, ys);  src_ye = min(Ny, ye)
    src_xs = max(0, xs);  src_xe = min(Nx, xe)

    if src_ys >= src_ye or src_xs >= src_xe:
        return patch  # 완전히 벗어난 경우 0 패치

    # 패치 내 대응 범위
    dst_ys = src_ys - ys;  dst_ye = dst_ys + (src_ye - src_ys)
    dst_xs = src_xs - xs;  dst_xe = dst_xs + (src_xe - src_xs)

    patch[dst_ys:dst_ye, dst_xs:dst_xe] = arr[src_ys:src_ye, src_xs:src_xe]
    return patch


def insert_patch(arr: np.ndarray, patch: np.ndarray,
                 cy: int, cx: int) -> np.ndarray:
    """arr (fftshift 기준)에 패치를 (cy, cx) 중심으로 삽입."""
    arr = arr.copy()
    Ny, Nx = arr.shape
    ph, pw = patch.shape

    ys = cy - ph // 2
    xs = cx - pw // 2
    ye = ys + ph
    xe = xs + pw

    # 유효 대상 범위
    dst_ys = max(0, ys);  dst_ye = min(Ny, ye)
    dst_xs = max(0, xs);  dst_xe = min(Nx, xe)

    if dst_ys >= dst_ye or dst_xs >= dst_xe:
        return arr  # 완전히 벗어난 경우

    # 패치 내 대응 범위
    src_ys = dst_ys - ys;  src_ye = src_ys + (dst_ye - dst_ys)
    src_xs = dst_xs - xs;  src_xe = src_xs + (dst_xe - dst_xs)

    arr[dst_ys:dst_ye, dst_xs:dst_xe] = patch[src_ys:src_ye, src_xs:src_xe]
    return arr


# ---------------------------------------------------------------------------
# 순방향 모델 (forward model)
# ---------------------------------------------------------------------------

def forward_model(
    O_hr_fshift: np.ndarray,
    pupil: np.ndarray,
    cy: int, cx: int,
    lr_shape: tuple[int, int]
) -> np.ndarray:
    """
    고해상도 푸리에 스펙트럼에서 저해상도 이미지 강도 계산.

    Parameters
    ----------
    O_hr_fshift : 고해상도 복소 푸리에 스펙트럼 (fftshift 기준)
    pupil       : pupil 마스크 (fftshift 기준, HR 크기)
    cy, cx      : 이번 LED의 HR 스펙트럼 내 중심 픽셀
    lr_shape    : 저해상도 이미지 크기 (Ny_lr, Nx_lr)

    Returns
    -------
    I_lr : 저해상도 강도 이미지
    """
    ph, pw = lr_shape
    patch_f = extract_patch(O_hr_fshift * pupil, cy, cx, ph, pw)
    # fftshift된 HR 스펙트럼에서 추출한 패치는 ifftshift 없이 바로 ifft2
    # (경사 조명에 의한 선형 위상은 세기 계산 시 상쇄됨)
    lr_field = ifft2(patch_f)
    return np.abs(lr_field)**2


# ---------------------------------------------------------------------------
# FPM 복원 (Gerchberg-Saxton 스타일)
# ---------------------------------------------------------------------------

def reconstruct_fpm(
    images: np.ndarray,
    kx_arr: np.ndarray,
    ky_arr: np.ndarray,
    cfg: FPMConfig,
    callback=None
) -> dict:
    """
    FPM 복원 알고리즘.

    Parameters
    ----------
    images   : 저해상도 이미지 스택, shape (N_led, Ny_lr, Nx_lr)
    kx_arr   : 각 LED의 x 방향 공간 주파수 [rad/m], shape (N_led,)
    ky_arr   : 각 LED의 y 방향 공간 주파수 [rad/m], shape (N_led,)
    cfg      : FPMConfig 인스턴스
    callback : 선택적 콜백 함수 callback(iter_idx, O_hr) — 중간 결과 모니터링용

    Returns
    -------
    dict with keys:
        'amplitude'  : 복원된 고해상도 진폭
        'phase'      : 복원된 고해상도 위상 [rad]
        'spectrum'   : 고해상도 푸리에 스펙트럼 (complex)
        'errors'     : 반복당 평균 세기 오차 리스트
    """
    N_led, Ny_lr, Nx_lr = images.shape
    Ny_hr = Ny_lr * cfg.upsample_factor
    Nx_hr = Nx_lr * cfg.upsample_factor

    hr_shape = (Ny_hr, Nx_hr)
    lr_shape = (Ny_lr, Nx_lr)

    # pupil 마스크 (fftshift 기준)
    pupil = make_pupil_mask(cfg, hr_shape)

    # 고해상도 복소 스펙트럼 초기화 (상수 진폭, 0 위상)
    O_hr_fshift = np.ones(hr_shape, dtype=complex)

    # 각 LED의 HR 스펙트럼 중심 픽셀 미리 계산
    effective_px = cfg.pixel_size_object / cfg.upsample_factor
    cy_list = []
    cx_list = []
    for kx, ky in zip(kx_arr, ky_arr):
        cy = Ny_hr // 2 + int(np.round(ky / (2 * np.pi) * Ny_hr * effective_px))
        cx = Nx_hr // 2 + int(np.round(kx / (2 * np.pi) * Nx_hr * effective_px))
        cy_list.append(np.clip(cy, 0, Ny_hr - 1))
        cx_list.append(np.clip(cx, 0, Nx_hr - 1))

    errors = []

    for it in range(cfg.n_iterations):
        total_error = 0.0

        # LED를 랜덤하게 섞어서 갱신 (수렴 개선)
        order = np.random.permutation(N_led)

        for i in order:
            I_meas = images[i]           # 측정 강도
            cy, cx = cy_list[i], cx_list[i]

            # 1) 현재 추정치로 저해상도 패치 추출
            # (fftshift된 HR 스펙트럼에서 패치 추출 후 ifft2만 적용)
            patch_f = extract_patch(O_hr_fshift * pupil, cy, cx, Ny_lr, Nx_lr)
            lr_field = ifft2(patch_f)

            # 2) 세기 오차
            I_est = np.abs(lr_field)**2
            total_error += np.mean(np.abs(I_est - I_meas))

            # 3) 진폭 교체 (측정 강도로 강제)
            amp_meas = np.sqrt(np.maximum(I_meas, 0))
            amp_est  = np.abs(lr_field) + cfg.regularization
            lr_field_new = lr_field * (amp_meas / amp_est)

            # 4) 업데이트된 패치를 고해상도 스펙트럼에 반영
            # (fft2만 적용 - fftshift 없음, HR 스펙트럼과 동일한 도메인)
            patch_f_new = fft2(lr_field_new)

            # Gradient-based update (ePIE 스타일)
            pupil_patch = extract_patch(pupil, cy, cx, Ny_lr, Nx_lr)
            pupil_conj  = np.conj(pupil_patch)
            pupil_max2  = np.max(np.abs(pupil_patch)**2) + cfg.regularization

            delta_patch = pupil_conj / pupil_max2 * (patch_f_new - patch_f)

            # HR 스펙트럼 갱신
            update = insert_patch(np.zeros(hr_shape, dtype=complex),
                                  delta_patch, cy, cx)
            O_hr_fshift = O_hr_fshift + update

        avg_error = total_error / N_led
        errors.append(avg_error)

        if callback is not None:
            callback(it, O_hr_fshift)

        if (it + 1) % 10 == 0 or it == 0:
            print(f"  Iter {it+1:3d}/{cfg.n_iterations}  |  avg intensity error: {avg_error:.4f}")

    # 물체 공간으로 변환
    O_hr = ifft2(ifftshift(O_hr_fshift))

    return {
        'amplitude': np.abs(O_hr),
        'phase':     np.angle(O_hr),
        'spectrum':  O_hr_fshift,
        'errors':    errors,
    }


# ---------------------------------------------------------------------------
# 시뮬레이션 데이터 생성
# ---------------------------------------------------------------------------

def simulate_measurements(
    O_gt: np.ndarray,
    kx_arr: np.ndarray,
    ky_arr: np.ndarray,
    cfg: FPMConfig,
    noise_level: float = 0.01
) -> np.ndarray:
    """
    정답 고해상도 물체로부터 저해상도 이미지 스택 시뮬레이션.

    Parameters
    ----------
    O_gt        : 정답 고해상도 복소 물체, shape (Ny_hr, Nx_hr)
    kx_arr, ky_arr : LED 공간 주파수
    cfg         : FPMConfig
    noise_level : Poisson 노이즈 스케일 (0이면 노이즈 없음)

    Returns
    -------
    images : shape (N_led, Ny_lr, Nx_lr)
    """
    Ny_hr, Nx_hr = O_gt.shape
    Ny_lr = Ny_hr // cfg.upsample_factor
    Nx_lr = Nx_hr // cfg.upsample_factor
    N_led = len(kx_arr)

    pupil = make_pupil_mask(cfg, (Ny_hr, Nx_hr))
    O_hr_fshift = fftshift(fft2(O_gt))

    effective_px = cfg.pixel_size_object / cfg.upsample_factor
    images = np.zeros((N_led, Ny_lr, Nx_lr))

    for i, (kx, ky) in enumerate(zip(kx_arr, ky_arr)):
        cy = Ny_hr // 2 + int(np.round(ky / (2 * np.pi) * Ny_hr * effective_px))
        cx = Nx_hr // 2 + int(np.round(kx / (2 * np.pi) * Nx_hr * effective_px))
        cy = np.clip(cy, 0, Ny_hr - 1)
        cx = np.clip(cx, 0, Nx_hr - 1)

        I = forward_model(O_hr_fshift, pupil, cy, cx, (Ny_lr, Nx_lr))

        if noise_level > 0:
            max_I = np.max(I) + 1e-12
            photons = I / max_I / noise_level
            I = np.random.poisson(photons * 1e4).astype(float) / 1e4 * max_I

        images[i] = I

    return images
