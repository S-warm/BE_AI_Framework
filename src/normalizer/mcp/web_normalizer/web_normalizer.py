from playwright.sync_api import Page
from typing import List

from normalizer.standard_ui_node import StandardUINode
from normalizer.mcp.web_normalizer.extractors.dom_extractor import DomExtractor
from normalizer.mcp.web_normalizer.validators.web_node_validator import WebNodeValidator
from normalizer.mcp.web_normalizer.utils.web_node_converter import WebNodeConverter
from normalizer.mcp.web_normalizer.processors.image_processor import ImageProcessor

class WebNormalizer:
    """
    HTML DOM -> StandardUINode 변환
    
    렌더링된 모든 것을 최대한 추출
    판단(필터링)은 인지 저하 레이어에 위임
    """
    
    # 생성자
    def __init__(self, screenshot_cache=None):
        self.image_processor = ImageProcessor(screenshot_cache=screenshot_cache)
    
    def normalize(self, page: Page) -> List[StandardUINode]:
        """
        Playwright Page 객체를 받아 StandardUINode 리스트로 반환
        
        Returns:
            List[StandardUINode]: 변환된 노드 리스트
        """
        
        # 1. 모든 요소의 raw data 한 번에 추출 (1번 통신)
        all_raw_data = DomExtractor._extract_dom(page)
        
        # 2. 각 raw data 변환
        nodes = []
        for raw_data in all_raw_data:
            # 유효성 체크 (빈 요소나 보이지 않는 요소 등을 제외한 유효한 노드만)
            if not WebNodeValidator._is_valid_node(raw_data):
                continue
            
            # 변환
            node = WebNodeConverter._convert_to_node(raw_data)
            if node:
                nodes.append(node)
                
        # 2. 이미지 처리 파이프라인
        self.image_processor.process_images(page, nodes)
        
        return nodes