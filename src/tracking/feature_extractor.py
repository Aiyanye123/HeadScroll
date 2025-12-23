"""
M3: 特征提取模块
从人脸关键点提取 gaze_y、眨眼状态、头姿等特征
"""

from dataclasses import dataclass
from enum import Enum, auto
from typing import Optional, Tuple
import numpy as np

from .face_tracker import FaceLandmarks, FaceTracker


class BlinkState(Enum):
    """眨眼状态"""
    OPEN = auto()      # 眼睛睁开
    CLOSING = auto()   # 正在闭合
    CLOSED = auto()    # 眼睛闭合


@dataclass
class FeaturePacket:
    """特征数据包"""
    timestamp: float           # 帧时间戳
    gaze_y_raw: float         # 原始注视高度 [0,1]，值越大视线越向下
    confidence: float         # 置信度 [0,1]
    blink_state: BlinkState   # 眨眼状态
    ear: float                # Eye Aspect Ratio
    head_pitch: float         # 头部俯仰角（弧度）
    face_present: bool        # 是否检测到人脸


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
                head_pitch=0.0,
                face_present=False
            )
        
        # 提取注视高度
        gaze_y_raw, gaze_confidence = self._extract_gaze_y(landmarks)
        
        # 提取 EAR 和眨眼状态
        ear = self._calculate_ear(landmarks)
        blink_state = self._determine_blink_state(ear)
        
        # 提取头部俯仰角
        head_pitch = self._extract_head_pitch(landmarks)
        
        # 综合置信度
        confidence = self._calculate_confidence(landmarks, gaze_confidence, ear)
        
        return FeaturePacket(
            timestamp=timestamp,
            gaze_y_raw=gaze_y_raw,
            confidence=confidence,
            blink_state=blink_state,
            ear=ear,
            head_pitch=head_pitch,
            face_present=True
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
        """
        提取头部俯仰角
        
        使用鼻尖和下巴的相对位置估计
        """
        try:
            nose = landmarks.get_point(FaceTracker.NOSE_TIP)
            chin = landmarks.get_point(FaceTracker.CHIN)
            
            # 简化估计：基于鼻尖和下巴的 y 差值
            # 正值表示抬头，负值表示低头
            dy = chin[1] - nose[1]
            dz = chin[2] - nose[2]
            
            # 估计俯仰角
            if abs(dy) < 0.001:
                return 0.0
            
            pitch = np.arctan2(dz, dy)
            return float(pitch)
            
        except Exception:
            return 0.0
    
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
