#src/normalizer/mcp/web_normalizer/processor/image_processor.py

from playwright.sync_api import Page
from typing import List
from PIL import Image
import io

from normalizer.standard_ui_node import StandardUINode
from normalizer.utils.image_vision.vision_cache import VisionCache
from normalizer.utils.image_vision.visoin_analyzer import VisionAnalyzer
from normalizer.utils.image_analyzer.image_color_extractor import ImageColorExtractor
from normalizer.utils.image_analyzer.image_classifier import ImageClassifier
from AI.cache.screenshot_cache import ScreenshotCache

class ImageProcessor:
    
    def __init__(self, screenshot_cache=None):
        self.vision_cache = VisionCache()
        self.vision_analyzer = VisionAnalyzer(cache=self.vision_cache)
        self.screenshot_cache = screenshot_cache or ScreenshotCache()
    
    def process_images(self, page: Page, nodes: List[StandardUINode]):
        """
        이미지 노드에 Vision API 분석 + 색상 추출 + 크기 분류
        
        파이프라인:
        1. 이미지 노드 필터링
        2. IQR 크기 분류
        3. 각 이미지 crop
        4. Vision API 호출 (캐싱)
        5. should_extract_color() 판단
        6. PIL 색상 추출 (조건부)
        7. StandardUINode 업데이트
        """
        try:
            # 1. 이미지 노드 필터링
            image_nodes = [n for n in nodes if n.type in ['image', 'icon']]
            
            if not image_nodes:
                return
            
            # 2. 전체 페이지 스크린샷 1회
            print("전체 페이지 스크린샷 촬영 중...")
            full_screenshot = page.screenshot(full_page=True)
            img = Image.open(io.BytesIO(full_screenshot))
            print(f"스크린샷 완료: {img.size}")
            
            # 2-1. 전체 스크린샷 캐싱
            if self.screenshot_cache:
                self.screenshot_cache.save(page.url, full_screenshot)
            
            # 3. IQR 크기 분류
            all_areas = [
                n.properties.get('width', 0) * n.properties.get('height', 0)
                for n in image_nodes
            ]
            
            for node in image_nodes:
                area = node.properties.get('width', 0) * node.properties.get('height', 0)
                node.image_tier = ImageClassifier.classify_image_size(area, all_areas)
            
            # 4-8. 각 이미지 처리
            for node in image_nodes:
                try:
                    # 4. PIL로 Crop
                    x = node.properties.get('x', 0)
                    y = node.properties.get('y', 0)
                    width = node.properties.get('width', 0)
                    height = node.properties.get('height', 0)
                    
                    # bbox 검증
                    if x < 0 or y < 0 or width <= 0 or height <= 0:
                        node.image_analysis = None
                        continue
                    
                    # 이미지 크기 초과 체크
                    if x + width > img.width or y + height > img.height:
                        node.image_analysis = None
                        continue
                    
                    # PIL crop
                    cropped = img.crop((x, y, x + width, y + height))
                    
                    # BytesIO로 변환
                    buffer = io.BytesIO()
                    cropped.save(buffer, format='PNG')
                    image_bytes = buffer.getvalue()
                    
                    # 5. Vision API 호출 (캐싱)
                    vision_result = self.vision_analyzer.analyze(image_bytes)
                    
                    # 6-7. 색상 추출 (조건부)
                    if self.vision_analyzer.should_extract_color(vision_result['type']):
                        dominant_color = ImageColorExtractor.extract_dominant_color(image_bytes)
                    else:
                        dominant_color = None
                    
                    # 8. StandardUINode 업데이트
                    node.image_analysis = {
                        'dominant_color': dominant_color,
                        'vision_type': vision_result['type'],
                        'vision_description': vision_result['description']
                    }
                    
                except Exception as e:
                    # 개별 이미지 처리 실패 시 스킵 (전체 파이프라인은 계속)
                    print(f"Failed to process image: {e}")
                    node.image_analysis = None
                    
        except Exception as e:
            # 전체 이미지 처리 실패 시 경고만 (DOM 파싱은 성공했으므로)
            print(f"Image processing pipeline failed: {e}")