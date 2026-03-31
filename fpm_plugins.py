"""
FPM Plugin System
=================
확장 가능한 플러그인 시스템으로 FPM 복원 파이프라인의 각 단계를 커스터마이즈할 수 있습니다.

플러그인 훅:
  - preprocess       : 복원 시작 전 이미지 전처리
  - before_iteration : 각 반복 시작 전 호출
  - on_update        : LED별 스펙트럼 업데이트 수정
  - after_iteration  : 각 반복 완료 후 호출
  - postprocess      : 복원 완료 후 결과 후처리

사용 예시:
    manager = PluginManager()
    manager.register(NoiseReductionPlugin(sigma=1.0))
    manager.register(ConvergenceMonitorPlugin(patience=5))
    result = reconstruct_fpm(images, kx, ky, cfg, plugin_manager=manager)
"""

from __future__ import annotations

import numpy as np
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


class FPMPlugin(ABC):
    """FPM 복원 파이프라인 플러그인 기본 클래스.

    서브클래스는 필요한 훅 메서드만 오버라이드하면 됩니다.
    """

    @property
    def name(self) -> str:
        """플러그인 이름 (기본: 클래스 이름)."""
        return self.__class__.__name__

    @property
    def priority(self) -> int:
        """실행 우선순위 (낮을수록 먼저 실행, 기본: 100)."""
        return 100

    def preprocess(self, images: np.ndarray, cfg: Any) -> np.ndarray:
        """복원 시작 전 이미지 전처리.

        Parameters
        ----------
        images : 저해상도 이미지 스택 (N_led, Ny_lr, Nx_lr)
        cfg    : FPMConfig 인스턴스

        Returns
        -------
        전처리된 이미지 스택
        """
        return images

    def before_iteration(self, iteration: int, O_hr_fshift: np.ndarray,
                         cfg: Any) -> np.ndarray:
        """각 반복 시작 전 호출.

        Parameters
        ----------
        iteration   : 현재 반복 인덱스 (0-based)
        O_hr_fshift : 고해상도 푸리에 스펙트럼 (fftshift 기준)
        cfg         : FPMConfig 인스턴스

        Returns
        -------
        수정된 스펙트럼
        """
        return O_hr_fshift

    def on_update(self, delta_patch: np.ndarray, led_index: int,
                  iteration: int, cfg: Any) -> np.ndarray:
        """LED별 스펙트럼 업데이트 델타 수정.

        Parameters
        ----------
        delta_patch : 업데이트 패치 (Ny_lr, Nx_lr)
        led_index   : 현재 LED 인덱스
        iteration   : 현재 반복 인덱스
        cfg         : FPMConfig 인스턴스

        Returns
        -------
        수정된 업데이트 패치
        """
        return delta_patch

    def after_iteration(self, iteration: int, O_hr_fshift: np.ndarray,
                        avg_error: float, cfg: Any) -> np.ndarray:
        """각 반복 완료 후 호출.

        Parameters
        ----------
        iteration   : 현재 반복 인덱스
        O_hr_fshift : 고해상도 푸리에 스펙트럼
        avg_error   : 이번 반복의 평균 세기 오차
        cfg         : FPMConfig 인스턴스

        Returns
        -------
        수정된 스펙트럼
        """
        return O_hr_fshift

    def postprocess(self, result: dict, cfg: Any) -> dict:
        """복원 완료 후 결과 후처리.

        Parameters
        ----------
        result : 복원 결과 dict (amplitude, phase, spectrum, errors)
        cfg    : FPMConfig 인스턴스

        Returns
        -------
        수정된 결과 dict
        """
        return result


class PluginManager:
    """플러그인 등록 및 실행을 관리합니다."""

    def __init__(self):
        self._plugins: list[FPMPlugin] = []

    @property
    def plugins(self) -> list[FPMPlugin]:
        return list(self._plugins)

    def register(self, plugin: FPMPlugin) -> PluginManager:
        """플러그인 등록. 메서드 체이닝 지원."""
        self._plugins.append(plugin)
        self._plugins.sort(key=lambda p: p.priority)
        return self

    def unregister(self, name: str) -> bool:
        """이름으로 플러그인 제거. 제거 성공 시 True 반환."""
        before = len(self._plugins)
        self._plugins = [p for p in self._plugins if p.name != name]
        return len(self._plugins) < before

    def run_preprocess(self, images: np.ndarray, cfg: Any) -> np.ndarray:
        for plugin in self._plugins:
            images = plugin.preprocess(images, cfg)
        return images

    def run_before_iteration(self, iteration: int, O_hr_fshift: np.ndarray,
                             cfg: Any) -> np.ndarray:
        for plugin in self._plugins:
            O_hr_fshift = plugin.before_iteration(iteration, O_hr_fshift, cfg)
        return O_hr_fshift

    def run_on_update(self, delta_patch: np.ndarray, led_index: int,
                      iteration: int, cfg: Any) -> np.ndarray:
        for plugin in self._plugins:
            delta_patch = plugin.on_update(delta_patch, led_index, iteration, cfg)
        return delta_patch

    def run_after_iteration(self, iteration: int, O_hr_fshift: np.ndarray,
                            avg_error: float, cfg: Any) -> np.ndarray:
        for plugin in self._plugins:
            O_hr_fshift = plugin.after_iteration(iteration, O_hr_fshift,
                                                  avg_error, cfg)
        return O_hr_fshift

    def run_postprocess(self, result: dict, cfg: Any) -> dict:
        for plugin in self._plugins:
            result = plugin.postprocess(result, cfg)
        return result


# ---------------------------------------------------------------------------
# Built-in Plugins
# ---------------------------------------------------------------------------

class NoiseReductionPlugin(FPMPlugin):
    """저해상도 입력 이미지에 가우시안 필터를 적용하여 노이즈를 줄입니다.

    Parameters
    ----------
    sigma : 가우시안 필터 표준편차 (픽셀 단위)
    """

    def __init__(self, sigma: float = 1.0):
        self.sigma = sigma

    @property
    def priority(self) -> int:
        return 10  # 전처리이므로 높은 우선순위

    def preprocess(self, images: np.ndarray, cfg: Any) -> np.ndarray:
        from scipy.ndimage import gaussian_filter
        filtered = np.empty_like(images)
        for i in range(images.shape[0]):
            filtered[i] = gaussian_filter(images[i], sigma=self.sigma)
        return filtered


class AdaptiveRegularizationPlugin(FPMPlugin):
    """반복 진행에 따라 정규화 계수를 감소시킵니다.

    초기 반복에서는 큰 정규화로 안정성을 확보하고,
    후반 반복에서는 작은 정규화로 정밀도를 높입니다.

    Parameters
    ----------
    initial_factor : 초기 정규화 배수 (cfg.regularization에 곱해짐)
    decay_rate     : 지수 감쇠율
    """

    def __init__(self, initial_factor: float = 10.0, decay_rate: float = 0.1):
        self.initial_factor = initial_factor
        self.decay_rate = decay_rate

    def before_iteration(self, iteration: int, O_hr_fshift: np.ndarray,
                         cfg: Any) -> np.ndarray:
        scale = self.initial_factor * np.exp(-self.decay_rate * iteration)
        cfg.regularization = cfg.regularization * max(scale, 1.0)
        return O_hr_fshift


class ConvergenceMonitorPlugin(FPMPlugin):
    """수렴 조건을 모니터링하고 조기 종료를 지원합니다.

    Parameters
    ----------
    patience   : 오차 개선이 없는 연속 반복 허용 횟수
    min_delta  : 최소 오차 감소량 (이보다 작으면 개선 없음으로 간주)
    """

    def __init__(self, patience: int = 5, min_delta: float = 1e-5):
        self.patience = patience
        self.min_delta = min_delta
        self._best_error = float('inf')
        self._wait = 0
        self.converged = False
        self.converged_at: int | None = None

    @property
    def priority(self) -> int:
        return 200  # 후처리 성격이므로 낮은 우선순위

    def after_iteration(self, iteration: int, O_hr_fshift: np.ndarray,
                        avg_error: float, cfg: Any) -> np.ndarray:
        if avg_error < self._best_error - self.min_delta:
            self._best_error = avg_error
            self._wait = 0
        else:
            self._wait += 1

        if self._wait >= self.patience and not self.converged:
            self.converged = True
            self.converged_at = iteration
            print(f"  [ConvergenceMonitor] 수렴 감지: iter {iteration + 1} "
                  f"(patience={self.patience} 초과)")

        return O_hr_fshift

    def postprocess(self, result: dict, cfg: Any) -> dict:
        result['convergence_info'] = {
            'converged': self.converged,
            'converged_at': self.converged_at,
            'best_error': self._best_error,
        }
        return result


class IntensityCorrectionPlugin(FPMPlugin):
    """LED별 강도 불균일을 보정합니다.

    각 LED 이미지의 평균 강도를 기준으로 정규화하여
    LED 밝기 차이에 의한 복원 오류를 줄입니다.
    """

    @property
    def priority(self) -> int:
        return 20

    def preprocess(self, images: np.ndarray, cfg: Any) -> np.ndarray:
        means = images.mean(axis=(1, 2), keepdims=True)
        global_mean = means.mean()
        # 평균 강도가 0인 이미지는 보정하지 않음
        safe_means = np.where(means > 1e-12, means, 1.0)
        return images * (global_mean / safe_means)


class SpectralConstraintPlugin(FPMPlugin):
    """고해상도 스펙트럼에 부드러운 경계 제약을 적용합니다.

    합성 개구의 경계에서 급격한 불연속을 방지하기 위해
    가우시안 윈도우를 적용합니다.

    Parameters
    ----------
    rolloff_width : 경계 부드러움 폭 (픽셀 단위)
    """

    def __init__(self, rolloff_width: float = 3.0):
        self.rolloff_width = rolloff_width
        self._window = None

    @property
    def priority(self) -> int:
        return 150

    def after_iteration(self, iteration: int, O_hr_fshift: np.ndarray,
                        avg_error: float, cfg: Any) -> np.ndarray:
        # 매 10번째 반복에서만 적용 (성능 고려)
        if iteration % 10 != 9:
            return O_hr_fshift

        if self._window is None or self._window.shape != O_hr_fshift.shape:
            Ny, Nx = O_hr_fshift.shape
            Y, X = np.ogrid[:Ny, :Nx]
            cy, cx = Ny // 2, Nx // 2
            r = np.sqrt((Y - cy)**2 + (X - cx)**2)
            r_max = min(Ny, Nx) // 2
            self._window = np.where(
                r <= r_max - self.rolloff_width,
                1.0,
                np.exp(-0.5 * ((r - r_max + self.rolloff_width)
                               / self.rolloff_width)**2)
            )

        return O_hr_fshift * self._window

    def postprocess(self, result: dict, cfg: Any) -> dict:
        result['spectral_constraint_applied'] = True
        return result
