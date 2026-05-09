#src/normalizer/utils/image_analyzer/image_color_extractor.py

from sklearn.cluster import KMeans
import numpy as np
from PIL import Image
import io

class ImageColorExtractor:
    """
    이미지 색상 추출 모듈

    K-means 클러스터링으로 지배적 색상 추출
    """
    
    @staticmethod
    def extract_dominant_color(image_bytes: bytes) -> tuple[int, int, int]:
        """
        K-means 클러스터링으로 지배적 색상 추출
        
        배경 + 소수 UI 요소 상황에서도 정확하게 버튼/아이콘 색상 추출.
        100x100으로 리사이즈 후 3개 클러스터로 분류, 가장 많은 클러스터의 중심색 반환.
        
        ⚠️ 주의: 이 함수는 색상 추출 여부를 판단하지 않음.
        호출 전에 VisionAnalyzer.should_extract_color()로 확인할 것.
        
        Args:
            image_bytes: 이미지 바이트 데이터
        
        Returns:
            (r, g, b) tuple (0-255)
        
        Raises:
            ValueError: 이미지 형식 오류
            RuntimeError: 예상 못한 에러
        
        Example:
            >>> with open('button.png', 'rb') as f:
            ...     img_bytes = f.read()
            >>> color = extract_dominant_color(img_bytes)
            >>> color
            (220, 50, 40)  # 빨강
        """
        try:
            img = Image.open(io.BytesIO(image_bytes))
            
            # RGB로 변환 (RGBA는 흰 배경 합성)
            if img.mode == 'RGBA':
                bg = Image.new('RGB', img.size, (255, 255, 255))
                bg.paste(img, mask=img.split()[3])
                img = bg
            elif img.mode != 'RGB':
                img = img.convert('RGB')
            
            # 성능 위해 리사이즈 (100x100이면 충분)
            img = img.resize((100, 100))
            
            # 픽셀 배열로 변환
            pixels = np.array(img).reshape(-1, 3)
            
            # K-means로 주요 색상 3개 클러스터링
            kmeans = KMeans(n_clusters=3, random_state=42, n_init=10)
            kmeans.fit(pixels)
            
            # 가장 많은 픽셀을 가진 클러스터 = dominant color
            labels, counts = np.unique(kmeans.labels_, return_counts=True)
            dominant_idx = labels[np.argmax(counts)]
            dominant_color = kmeans.cluster_centers_[dominant_idx]
            
            r, g, b = dominant_color.astype(int)
            return (int(r), int(g), int(b))
            
        except (IOError, OSError) as e:
            raise ValueError(f"Invalid image format: {e}") from e
        except Exception as e:
            raise RuntimeError(f"Unexpected error in color extraction: {e}") from e