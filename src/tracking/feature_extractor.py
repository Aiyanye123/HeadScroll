"""
M3: 头姿特征提取模块
从人脸关键点和变换矩阵提取头部俯仰角
"""

from dataclasses import dataclass
from typing import Optional
import numpy as np

from .face_tracker import (
    FaceLandmarks,
    FaceTracker,
    HEAD_POSE_LEGACY_ALGORITHM,
    HEAD_POSE_MATRIX_ALGORITHM,
    HEAD_POSE_UNAVAILABLE,
)


@dataclass
class FeaturePacket:
    """头姿特征数据包"""
    timestamp: float           # 帧时间戳
    head_pitch: float         # 弧度，低头增大；相对中立值由标定中心计算，无效时为 NaN
    face_present: bool        # 是否检测到人脸
    head_pose_valid: bool = False
    head_pose_algorithm: str = HEAD_POSE_UNAVAILABLE


class FeatureExtractor:
    """头姿特征提取器"""
    
    def extract(
        self,
        landmarks: Optional[FaceLandmarks],
        timestamp: float
    ) -> FeaturePacket:
        """
        从关键点提取特征
        
        Args:
            landmarks: 人脸关键点数据
            timestamp: 帧时间戳
            
        Returns:
            特征数据包
        """
        if landmarks is None:
            return FeaturePacket(
                timestamp=timestamp,
                head_pitch=float("nan"),
                face_present=False
            )
        
        head_pitch = self._extract_head_pitch(landmarks)
        
        return FeaturePacket(
            timestamp=timestamp,
            head_pitch=head_pitch,
            face_present=True,
            head_pose_valid=bool(np.isfinite(head_pitch)),
            head_pose_algorithm=landmarks.head_pose_algorithm,
        )
    
    def _extract_head_pitch(self, landmarks: FaceLandmarks) -> float:
        """Return pitch in radians, increasing downward; calibration removes neutral bias."""
        if landmarks.head_pose_algorithm == HEAD_POSE_MATRIX_ALGORITHM:
            return self._matrix_head_pitch(landmarks.facial_transformation_matrix)
        if landmarks.head_pose_algorithm == HEAD_POSE_LEGACY_ALGORITHM:
            return self._landmark_head_pitch(landmarks)
        return float("nan")

    @staticmethod
    def _matrix_head_pitch(matrix: Optional[np.ndarray]) -> float:
        """Extract X rotation from MediaPipe's canonical-to-runtime metric transform."""
        if matrix is None:
            return float("nan")
        try:
            transform = np.asarray(matrix, dtype=np.float64)
            if transform.shape != (4, 4) or not np.isfinite(transform).all():
                return float("nan")
            if not np.allclose(transform[3], [0, 0, 0, 1], atol=1e-6):
                return float("nan")

            # Polar decomposition removes scale before reading rotation components.
            left, scales, right = np.linalg.svd(transform[:3, :3])
            if scales[0] <= 0 or scales[-1] <= scales[0] * 1e-6:
                return float("nan")
            rotation = left @ right
            if np.linalg.det(rotation) <= 0:
                return float("nan")

            # R = Rz(roll) Ry(yaw) Rx(pitch); reject the yaw gimbal singularity.
            if np.hypot(rotation[2, 1], rotation[2, 2]) < 1e-6:
                return float("nan")
            # Metric Y points up and Z toward the camera: positive X pitch is down.
            return float(np.arctan2(rotation[2, 1], rotation[2, 2]))
        except (TypeError, ValueError, np.linalg.LinAlgError):
            return float("nan")

    @staticmethod
    def _landmark_head_pitch(landmarks: FaceLandmarks) -> float:
        """Legacy two-point estimate, with Y and Z expressed in matching pixel units."""
        if landmarks.image_width <= 0 or landmarks.image_height <= 0:
            return float("nan")
        try:
            nose = landmarks.get_point(FaceTracker.NOSE_TIP)
            chin = landmarks.get_point(FaceTracker.CHIN)
            dy = (chin[1] - nose[1]) * landmarks.image_height
            # MediaPipe screen Z is scaled like X, not Y.
            dz = (chin[2] - nose[2]) * landmarks.image_width
            if not np.isfinite([dy, dz]).all() or np.hypot(dy, dz) < 1e-6:
                return float("nan")
            return float(np.arctan2(dz, dy))
        except (IndexError, TypeError, ValueError):
            return float("nan")
