"""
M2: 人脸追踪模块
使用 MediaPipe Face Mesh 进行人脸关键点检测
"""

from dataclasses import dataclass
from typing import Optional
from pathlib import Path
import sys
import time
import urllib.request
import numpy as np
import shutil
import tempfile

import cv2
import mediapipe as mp

MODEL_URL = (
    "https://storage.googleapis.com/mediapipe-models/"
    "face_landmarker/face_landmarker/float16/1/face_landmarker.task"
)

HEAD_POSE_MATRIX_ALGORITHM = "face_matrix_pitch_v1"
HEAD_POSE_LEGACY_ALGORITHM = "face_landmark_pitch_v1"
HEAD_POSE_UNAVAILABLE = "unavailable"


@dataclass
class FaceLandmarks:
    """人脸关键点数据"""
    # 468 个人脸关键点 (x, y, z)
    landmarks: np.ndarray  # shape: (468, 3)
    # 图像尺寸
    image_width: int
    image_height: int
    facial_transformation_matrix: Optional[np.ndarray] = None
    head_pose_algorithm: str = HEAD_POSE_LEGACY_ALGORITHM
    
    def get_point(self, index: int) -> np.ndarray:
        """获取指定索引的关键点坐标 (x, y, z)"""
        return self.landmarks[index]
    
    def get_pixel_coords(self, index: int) -> tuple:
        """获取关键点的像素坐标 (px, py)"""
        point = self.landmarks[index]
        px = int(point[0] * self.image_width)
        py = int(point[1] * self.image_height)
        return px, py


class FaceTracker:
    """人脸追踪器- MediaPipe Face Mesh 封装"""
    
    # 头部姿态参考点
    NOSE_TIP = 1
    CHIN = 152
    
    def __init__(
        self,
        max_num_faces: int = 1,
        min_detection_confidence: float = 0.5,
        min_tracking_confidence: float = 0.5,
        model_path: Optional[str] = None
    ):
        """
        初始化人脸追踪器
        
        Args:
            max_num_faces: 最大检测人脸数
            min_detection_confidence: 最小检测置信度
            min_tracking_confidence: 最小追踪置信度
        """
        self._use_tasks = not hasattr(mp, "solutions")
        self._face_mesh = None
        self._face_landmarker = None

        if self._use_tasks:
            self._init_tasks_landmarker(
                max_num_faces=max_num_faces,
                min_detection_confidence=min_detection_confidence,
                min_tracking_confidence=min_tracking_confidence,
                model_path=model_path,
            )
        else:
            self._init_solutions_face_mesh(
                max_num_faces=max_num_faces,
                min_detection_confidence=min_detection_confidence,
                min_tracking_confidence=min_tracking_confidence,
            )

    @property
    def head_pose_algorithm(self) -> str:
        """Return the fixed pose algorithm selected for this tracker backend."""
        if self._use_tasks:
            return HEAD_POSE_MATRIX_ALGORITHM
        return HEAD_POSE_LEGACY_ALGORITHM
    
    def _init_solutions_face_mesh(
        self,
        max_num_faces: int,
        min_detection_confidence: float,
        min_tracking_confidence: float,
    ) -> None:
        self.mp_face_mesh = mp.solutions.face_mesh
        self._face_mesh = self.mp_face_mesh.FaceMesh(
            max_num_faces=max_num_faces,
            refine_landmarks=False,
            min_detection_confidence=min_detection_confidence,
            min_tracking_confidence=min_tracking_confidence,
        )

    def _init_tasks_landmarker(
        self,
        max_num_faces: int,
        min_detection_confidence: float,
        min_tracking_confidence: float,
        model_path: Optional[str],
    ) -> None:
        from mediapipe.tasks import python as mp_tasks
        from mediapipe.tasks.python import vision

        model_file = self._resolve_model_path(model_path)
        self._ensure_model_file(model_file)
        model_file = self._ensure_ascii_model_path(model_file)

        options = vision.FaceLandmarkerOptions(
            base_options=mp_tasks.BaseOptions(model_asset_path=str(model_file)),
            running_mode=vision.RunningMode.VIDEO,
            num_faces=max_num_faces,
            min_face_detection_confidence=min_detection_confidence,
            min_face_presence_confidence=min_tracking_confidence,
            min_tracking_confidence=min_tracking_confidence,
            output_facial_transformation_matrixes=True,
        )
        self._face_landmarker = vision.FaceLandmarker.create_from_options(options)

    def _resolve_model_path(self, model_path: Optional[str]) -> Path:
        if model_path:
            return Path(model_path).expanduser()
        if getattr(sys, "frozen", False):
            exe_dir = Path(sys.executable).resolve().parent
            candidates = []
            if hasattr(sys, "_MEIPASS"):
                candidates.append(Path(sys._MEIPASS) / "assets" / "models" / "face_landmarker.task")
            candidates.append(exe_dir / "assets" / "models" / "face_landmarker.task")
            candidates.append(exe_dir / "_internal" / "assets" / "models" / "face_landmarker.task")
            for candidate in candidates:
                if candidate.exists():
                    return candidate
            return candidates[0] if candidates else exe_dir / "assets" / "models" / "face_landmarker.task"
        repo_root = Path(__file__).resolve().parents[2]
        return repo_root / "assets" / "models" / "face_landmarker.task"

    def _ensure_model_file(self, model_file: Path) -> None:
        if model_file.exists():
            return
        model_file.parent.mkdir(parents=True, exist_ok=True)
        try:
            urllib.request.urlretrieve(MODEL_URL, model_file)
        except Exception as exc:
            raise RuntimeError(
                f"Failed to download face landmarker model to {model_file}. "
                f"Please download it manually from {MODEL_URL}."
            ) from exc

    def _ensure_ascii_model_path(self, model_file: Path) -> Path:
        try:
            str(model_file).encode("ascii")
            return model_file
        except UnicodeEncodeError:
            pass
        temp_root = Path(tempfile.gettempdir()) / "EyeScroll" / "models"
        temp_root.mkdir(parents=True, exist_ok=True)
        temp_path = temp_root / model_file.name
        if model_file.exists():
            shutil.copy2(model_file, temp_path)
        else:
            self._ensure_model_file(temp_path)
        return temp_path

    def process(self, frame: np.ndarray) -> Optional[FaceLandmarks]:
        """
        处理一帧图像，提取人脸关键点
        
        Args:
            frame: BGR 格式的图像帧
            
        Returns:
            人脸关键点数据，未检测到人脸时返回 None
        """
        # 转换为 RGB
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        h, w = frame.shape[:2]
        facial_transformation_matrix = None

        if self._use_tasks:
            mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb_frame)
            results = self._face_landmarker.detect_for_video(
                mp_image, int(time.perf_counter() * 1000)
            )
            if not results.face_landmarks:
                return None

            if results.facial_transformation_matrixes:
                facial_transformation_matrix = np.asarray(
                    results.facial_transformation_matrixes[0], dtype=np.float64
                )

            face_landmarks = results.face_landmarks[0][:468]
            num_landmarks = len(face_landmarks)
            landmarks = np.zeros((num_landmarks, 3), dtype=np.float32)
            for i, lm in enumerate(face_landmarks):
                landmarks[i] = [lm.x, lm.y, lm.z]
        else:
            results = self._face_mesh.process(rgb_frame)
            if not results.multi_face_landmarks:
                return None

            face_landmarks = results.multi_face_landmarks[0]
            num_landmarks = 468
            landmarks = np.zeros((num_landmarks, 3), dtype=np.float32)
            for i, lm in enumerate(face_landmarks.landmark):
                if i >= num_landmarks:
                    break
                landmarks[i] = [lm.x, lm.y, lm.z]
        
        return FaceLandmarks(
            landmarks=landmarks,
            image_width=w,
            image_height=h,
            facial_transformation_matrix=facial_transformation_matrix,
            head_pose_algorithm=self.head_pose_algorithm,
        )
    
    def close(self) -> None:
        """释放资源"""
        if self._use_tasks:
            if self._face_landmarker:
                self._face_landmarker.close()
        else:
            if self._face_mesh:
                self._face_mesh.close()
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
        return False
