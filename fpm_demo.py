"""
FPM 데모 스크립트
=================
시뮬레이션된 저해상도 이미지로 FPM 복원을 실행하고 결과를 시각화합니다.

실행:
    python fpm_demo.py

의존 패키지:
    numpy, matplotlib, scikit-image (선택)
"""

import numpy as np
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
from numpy.fft import fft2, ifft2, fftshift

from fpm_reconstruction import (
    FPMConfig,
    compute_led_positions,
    simulate_measurements,
    reconstruct_fpm,
    make_pupil_mask,
)


# ---------------------------------------------------------------------------
# 정답 고해상도 복소 물체 생성
# ---------------------------------------------------------------------------

def make_ground_truth(Ny: int, Nx: int) -> np.ndarray:
    """
    진폭: 텍스트/슬릿 패턴, 위상: 부드러운 렌즈 형상
    → 현실적인 위상 물체(투명 생체 시료 근사)
    """
    # 진폭 패턴 (사각 슬릿)
    amp = np.ones((Ny, Nx))
    # 수평 줄무늬
    for y in range(0, Ny, Ny // 8):
        amp[y:y + Ny // 40, :] = 0.3
    # 수직 줄무늬 (일부)
    for x in range(0, Nx // 2, Nx // 12):
        amp[:, x:x + Nx // 60] = 0.3

    # 원형 마스크로 테두리 처리
    Y, X = np.ogrid[:Ny, :Nx]
    cy, cx = Ny // 2, Nx // 2
    r = np.sqrt((Y - cy)**2 + (X - cx)**2)
    amp *= (r < 0.45 * min(Ny, Nx)).astype(float)

    # 위상 패턴 (이중 가우시안 렌즈)
    sigma = min(Ny, Nx) / 5
    phase = 2.5 * np.exp(-((Y - cy * 0.8)**2 + (X - cx * 0.8)**2) / (2 * sigma**2))
    phase -= 1.5 * np.exp(-((Y - cy * 1.2)**2 + (X - cx * 1.2)**2) / (2 * (sigma * 0.6)**2))

    return amp * np.exp(1j * phase)


# ---------------------------------------------------------------------------
# 결과 시각화
# ---------------------------------------------------------------------------

def visualize(
    O_gt: np.ndarray,
    images: np.ndarray,
    result: dict,
    cfg: FPMConfig,
    kx_arr: np.ndarray,
    ky_arr: np.ndarray,
):
    fig = plt.figure(figsize=(16, 10))
    fig.suptitle("Fourier Ptychographic Microscopy — 복원 결과", fontsize=14, fontweight='bold')
    gs = gridspec.GridSpec(3, 4, figure=fig, hspace=0.45, wspace=0.35)

    # ---- 정답 ----
    ax = fig.add_subplot(gs[0, 0])
    ax.imshow(np.abs(O_gt), cmap='gray')
    ax.set_title("GT 진폭 (고해상도)")
    ax.axis('off')

    ax = fig.add_subplot(gs[0, 1])
    ax.imshow(np.angle(O_gt), cmap='hsv', vmin=-np.pi, vmax=np.pi)
    ax.set_title("GT 위상 (고해상도)")
    ax.axis('off')

    # ---- 저해상도 샘플 이미지 ----
    center_idx = len(images) // 2
    ax = fig.add_subplot(gs[0, 2])
    ax.imshow(images[0], cmap='gray')
    ax.set_title(f"LR 이미지 #0\n(경사 조명)")
    ax.axis('off')

    ax = fig.add_subplot(gs[0, 3])
    ax.imshow(images[center_idx], cmap='gray')
    ax.set_title(f"LR 이미지 #{center_idx}\n(중앙 조명)")
    ax.axis('off')

    # ---- 복원 결과 ----
    ax = fig.add_subplot(gs[1, 0])
    ax.imshow(result['amplitude'], cmap='gray')
    ax.set_title("복원 진폭 (고해상도)")
    ax.axis('off')

    ax = fig.add_subplot(gs[1, 1])
    ax.imshow(result['phase'], cmap='hsv', vmin=-np.pi, vmax=np.pi)
    ax.set_title("복원 위상 (고해상도)")
    ax.axis('off')

    # ---- 스펙트럼 ----
    hr_shape = result['spectrum'].shape
    pupil = make_pupil_mask(cfg, hr_shape)

    ax = fig.add_subplot(gs[1, 2])
    spec = np.log1p(np.abs(result['spectrum']))
    ax.imshow(spec, cmap='inferno')
    ax.set_title("복원 주파수 스펙트럼\n(log scale)")
    ax.axis('off')

    # ---- LED 커버리지 맵 ----
    ax = fig.add_subplot(gs[1, 3])
    coverage = np.zeros(hr_shape)
    Ny_hr, Nx_hr = hr_shape
    eff_px = cfg.pixel_size_object / cfg.upsample_factor
    for kx, ky in zip(kx_arr, ky_arr):
        cy = Ny_hr // 2 + int(np.round(ky / (2 * np.pi) * Ny_hr * eff_px))
        cx = Nx_hr // 2 + int(np.round(kx / (2 * np.pi) * Nx_hr * eff_px))
        cy = np.clip(cy, 0, Ny_hr - 1)
        cx = np.clip(cx, 0, Nx_hr - 1)
        coverage[max(0, cy - 2):cy + 3, max(0, cx - 2):cx + 3] += 1.0
    ax.imshow(coverage, cmap='hot')
    ax.set_title("LED 주파수 커버리지")
    ax.axis('off')

    # ---- 수렴 곡선 ----
    ax = fig.add_subplot(gs[2, :2])
    ax.semilogy(result['errors'], 'b-o', markersize=3, linewidth=1.5)
    ax.set_xlabel("반복 횟수")
    ax.set_ylabel("평균 세기 오차 (log scale)")
    ax.set_title("수렴 곡선")
    ax.grid(True, alpha=0.4)

    # ---- 중앙 라인 프로파일 비교 ----
    ax = fig.add_subplot(gs[2, 2:])
    Ny_hr = result['amplitude'].shape[0]
    gt_down = np.abs(O_gt)  # 같은 크기

    mid = Ny_hr // 2
    ax.plot(gt_down[mid], 'k-', label='GT 진폭', linewidth=1.5, alpha=0.8)
    ax.plot(result['amplitude'][mid], 'r--', label='복원 진폭', linewidth=1.5, alpha=0.8)
    ax.set_xlabel("픽셀")
    ax.set_ylabel("진폭")
    ax.set_title("중앙 행 프로파일 비교")
    ax.legend()
    ax.grid(True, alpha=0.4)

    plt.savefig("fpm_result.png", dpi=150, bbox_inches='tight')
    print("\n결과 이미지 저장: fpm_result.png")
    plt.show()


# ---------------------------------------------------------------------------
# 메인
# ---------------------------------------------------------------------------

def main():
    print("=" * 60)
    print("  Fourier Ptychographic Microscopy 복원 데모")
    print("=" * 60)

    # 1) 시스템 설정
    cfg = FPMConfig(
        wavelength=0.532e-6,    # 녹색 레이저 [m]
        NA_obj=0.08,
        pixel_size_camera=6.5e-6,
        magnification=4.0,
        led_pitch=4e-3,
        led_distance=80e-3,
        upsample_factor=4,
        n_iterations=30,
        led_grid_size=11,       # 11x11 = 121개 LED
        regularization=1e-6,
    )

    print(f"\n시스템 파라미터:")
    print(f"  파장           : {cfg.wavelength*1e9:.0f} nm")
    print(f"  대물렌즈 NA    : {cfg.NA_obj}")
    print(f"  카메라 픽셀    : {cfg.pixel_size_camera*1e6:.1f} μm")
    print(f"  배율           : {cfg.magnification}x")
    print(f"  업샘플 배율    : {cfg.upsample_factor}x")
    print(f"  LED 격자       : {cfg.led_grid_size}x{cfg.led_grid_size} = {cfg.led_grid_size**2}개")
    print(f"  최대 조명 NA   : {cfg.NA_illumination_max:.3f}")

    # 2) LED 좌표 계산
    kx_arr, ky_arr = compute_led_positions(cfg)
    N_led = len(kx_arr)
    print(f"\nLED 수: {N_led}")

    # 3) 정답 고해상도 물체 생성
    Ny_lr, Nx_lr = 64, 64           # 저해상도 이미지 크기
    Ny_hr = Ny_lr * cfg.upsample_factor
    Nx_hr = Nx_lr * cfg.upsample_factor
    print(f"저해상도 이미지: {Ny_lr}x{Nx_lr}")
    print(f"고해상도 출력  : {Ny_hr}x{Nx_hr}")

    np.random.seed(42)
    O_gt = make_ground_truth(Ny_hr, Nx_hr)

    # 4) 순방향 모델로 저해상도 이미지 생성 (시뮬레이션)
    print("\n저해상도 이미지 시뮬레이션 중...")
    images = simulate_measurements(O_gt, kx_arr, ky_arr, cfg, noise_level=0.02)
    print(f"  생성 완료: {images.shape} 형태, 강도 범위 [{images.min():.4f}, {images.max():.4f}]")

    # 5) FPM 복원
    print(f"\nFPM 복원 시작 (반복 횟수={cfg.n_iterations})...")
    result = reconstruct_fpm(images, kx_arr, ky_arr, cfg)

    # 6) 정량 평가
    amp_gt = np.abs(O_gt)
    amp_rec = result['amplitude']

    # 진폭 정규화 후 RMSE
    amp_gt_n = amp_gt / (amp_gt.max() + 1e-12)
    amp_rec_n = amp_rec / (amp_rec.max() + 1e-12)
    rmse = np.sqrt(np.mean((amp_gt_n - amp_rec_n)**2))
    print(f"\n정량 평가:")
    print(f"  진폭 RMSE (정규화): {rmse:.4f}")
    print(f"  최종 오차         : {result['errors'][-1]:.4f}")

    # 7) 시각화
    print("\n결과 시각화 중...")
    visualize(O_gt, images, result, cfg, kx_arr, ky_arr)

    print("\n완료!")


if __name__ == "__main__":
    main()
