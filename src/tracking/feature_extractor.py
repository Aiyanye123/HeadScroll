"""
M3: 头部姿态提取模块
从人脸变换矩阵或关键点提取头部俯仰角
"""

from dataclasses import dataclass
from enum import Enum, auto
from typing import Optional, Tuple
import numpy as np

from .face_tracker import (
    FaceLandmarks,
    FaceTracker,
    HEAD_POSE_LEGACY_ALGORITHM,
    HEAD_POSE_MATRIX_ALGORITHM,
    HEAD_POSE_UNAVAILABLE,
)


class BlinkState(Enum):
    """眨眼状态"""
    OPEN = auto()      # 眼睛睁开
    CLOSING = auto()   # 正在闭合
    CLOSED = auto()    # 眼睛闭合


@dataclass
class FeaturePacket:
    """特征数据包"""
    timestamp: float           # 帧时间戳
    gaze_y_raw: float         # Legacy packet field; head control does not use gaze.
    confidence: float         # 置信度 [0,1]
    blink_state: BlinkState   # Legacy packet field; no blink control is active.
    ear: float                # Legacy packet field; no EAR calculation is active.
    head_pitch: float         # 头部俯仰角（弧度）
    face_present: bool        # 是否检测到人脸
    head_pose_valid: bool = False
    head_pose_algorithm: str = HEAD_POSE_UNAVAILABLE


class FeatureExtractor:
    """特征提取器"""
    
    # EAR 阈值
    EAR_THRESHOLD_CLOSED = 0.2   # 低于此值认为眼睛闭合
    EAR_THRESHOLD_OPEN = 0.25    # 高于此值认为眼睛睁开
    
    def __init__(self):
        """初始化特征提取器"""
        self._prev_ear = 0.3  # 上一帧 EAR
        self._prev_blink_state = BlinkState.OPEN
    
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
                gaze_y_raw=0.5,
                confidence=0.0,
                blink_state=BlinkState.OPEN,
                ear=0.0,
                head_pitch=float("nan"),
                face_present=False
            )
        
        # 提取头部俯仰角
        head_pitch = self._extract_head_pitch(landmarks)
        
        return FeaturePacket(
            timestamp=timestamp,
            gaze_y_raw=0.5,
            confidence=float(np.isfinite(head_pitch)),
            blink_state=BlinkState.OPEN,
            ear=0.0,
            head_pitch=head_pitch,
            face_present=True,
            head_pose_valid=bool(np.isfinite(head_pitch)),
            head_pose_algorithm=landmarks.head_pose_algorithm,
        )
    
    def _extract_gaze_y(self, landmarks: FaceLandmarks) -> Tuple[float, float]:
        """
        提取注视高度（只做 y 方向）
        
        基于虹膜相对上下眼睑位置：
        g = (y_iris - y_top) / (y_bottom - y_top)
        
        Returns:
            (gaze_y_raw, confidence) 元组
        """
        try:
            # 左眼
            left_gaze, left_conf = self._single_eye_gaze_y(
                landmarks,
                iris_indices=FaceTracker.LEFT_IRIS,
                upper_indices=FaceTracker.LEFT_EYE_UPPER,
                lower_indices=FaceTracker.LEFT_EYE_LOWER
            )
            
            # 右眼
            right_gaze, right_conf = self._single_eye_gaze_y(
                landmarks,
                iris_indices=FaceTracker.RIGHT_IRIS,
                upper_indices=FaceTracker.RIGHT_EYE_UPPER,
                lower_indices=FaceTracker.RIGHT_EYE_LOWER
            )
            
            # 双眼融合（加权平均）
            total_conf = left_conf + right_conf
            if total_conf < 0.01:
                return 0.5, 0.0
            
            gaze_y = (left_gaze * left_conf + right_gaze * right_conf) / total_conf
            confidence = total_conf / 2.0
            
            # 裁剪到 [0, 1]
            gaze_y = np.clip(gaze_y, 0.0, 1.0)
            
            return float(gaze_y), float(confidence)
            
        except Exception:
            return 0.5, 0.0
    
    def _single_eye_gaze_y(
        self,
        landmarks: FaceLandmarks,
        iris_indices: list,
        upper_indices: list,
        lower_indices: list
    ) -> Tuple[float, float]:
        """计算单眼注视高度"""
        # 获取虹膜中心 y
        iris_points = landmarks.get_points(iris_indices)
        y_iris = np.mean(iris_points[:, 1])
        
        # 获取上眼睑 y（取平均或最小）
        upper_points = landmarks.get_points(upper_indices)
        y_top = np.mean(upper_points[:, 1])
        
        # 获取下眼睑 y（取平均或最大）
        lower_points = landmarks.get_points(lower_indices)
        y_bottom = np.mean(lower_points[:, 1])
        
        # 计算归一化位置
        eye_height = y_bottom - y_top
        if eye_height < 0.001:
            return 0.5, 0.0
        
        gaze_y = (y_iris - y_top) / eye_height
        
        # 置信度基于眼睛开合度
        confidence = min(eye_height * 50, 1.0)  # 简单启发式
        
        return gaze_y, confidence
    
    def _calculate_ear(self, landmarks: FaceLandmarks) -> float:
        """
        计算 Eye Aspect Ratio (EAR)
        
        EAR = (|p2-p6| + |p3-p5|) / (2 * |p1-p4|)
        """
        left_ear = self._single_eye_ear(landmarks, FaceTracker.LEFT_EYE_EAR)
        right_ear = self._single_eye_ear(landmarks, FaceTracker.RIGHT_EYE_EAR)
        
        ear = (left_ear + right_ear) / 2.0
        self._prev_ear = ear
        return ear
    
    def _single_eye_ear(self, landmarks: FaceLandmarks, indices: list) -> float:
        """计算单眼 EAR"""
        # indices: [p1, p2, p3, p4, p5, p6]
        points = landmarks.get_points(indices)
        
        # 垂直距离
        v1 = np.linalg.norm(points[1] - points[5])
        v2 = np.linalg.norm(points[2] - points[4])
        
        # 水平距离
        h = np.linalg.norm(points[0] - points[3])
        
        if h < 0.001:
            return 0.0
        
        return (v1 + v2) / (2.0 * h)
    
    def _determine_blink_state(self, ear: float) -> BlinkState:
        """根据 EAR 确定眨眼状态"""
        if ear < self.EAR_THRESHOLD_CLOSED:
            state = BlinkState.CLOSED
        elif ear < self.EAR_THRESHOLD_OPEN:
            # 迟滞区域，保持之前状态或判定为 CLOSING
            if self._prev_blink_state == BlinkState.OPEN:
                state = BlinkState.CLOSING
            else:
                state = self._prev_blink_state
        else:
            state = BlinkState.OPEN
        
        self._prev_blink_state = state
        return state
    
    def _extract_head_pitch(self, landmarks: FaceLandmarks) -> float:
        """Return downward-positive pitch using the tracker's fixed algorithm."""
        if landmarks.head_pose_algorithm == HEAD_POSE_MATRIX_ALGORITHM:
            return self._matrix_head_pitch(landmarks.transformation_matrix)
        if landmarks.head_pose_algorithm == HEAD_POSE_LEGACY_ALGORITHM:
            return self._landmark_head_pitch(landmarks)
        return float("nan")

    @staticmethod
    def _matrix_head_pitch(matrix: Optional[np.ndarray]) -> float:
        try:
            transform = np.asarray(matrix, dtype=np.float64)
            if transform.shape != (4, 4) or not np.isfinite(transform).all():
                return float("nan")
            if not np.allclose(transform[3], [0, 0, 0, 1], atol=1e-6):
                return float("nan")
            # Remove scale before interpreting the canonical-to-runtime rotation.
            left, scales, right = np.linalg.svd(transform[:3, :3])
            if scales[0] <= 0 or scales[-1] <= scales[0] * 1e-6:
                return float("nan")
            rotation = left @ right
            if np.linalg.det(rotation) <= 0:
                return float("nan")
            if np.hypot(rotation[2, 1], rotation[2, 2]) < 1e-6:
                return float("nan")
            return float(np.arctan2(rotation[2, 1], rotation[2, 2]))
        except (TypeError, ValueError, np.linalg.LinAlgError):
            return float("nan")

    @staticmethod
    def _landmark_head_pitch(landmarks: FaceLandmarks) -> float:
        if landmarks.image_width <= 0 or landmarks.image_height <= 0:
            return float("nan")
        try:
            nose = landmarks.get_point(FaceTracker.NOSE_TIP)
            chin = landmarks.get_point(FaceTracker.CHIN)
            dy = (chin[1] - nose[1]) * landmarks.image_height
            # MediaPipe screen Z uses the same scale as X.
            dz = (chin[2] - nose[2]) * landmarks.image_width
            if not np.isfinite([dy, dz]).all() or np.hypot(dy, dz) < 1e-6:
                return float("nan")
            return float(np.arctan2(dz, dy))
        except (IndexError, TypeError, ValueError):
            return float("nan")
    
    def _calculate_confidence(
        self,
        landmarks: FaceLandmarks,
        gaze_confidence: float,
        ear: float
    ) -> float:
        """计算综合置信度"""
        # 基础置信度来自注视估计
        confidence = gaze_confidence
        
        # 如果眼睛过于闭合，降低置信度
        if ear < self.EAR_THRESHOLD_CLOSED:
            confidence *= 0.6
        elif ear < self.EAR_THRESHOLD_OPEN:
            confidence *= 0.85
        
        return np.clip(confidence, 0.0, 1.0)
