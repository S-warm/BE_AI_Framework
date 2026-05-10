#src/normalizer/mcp/web_normalizer/utils/web_node_converter.py

from typing import Dict, Any
from normalizer.standard_ui_node import StandardUINode
from ..extractors.type_extractor import TypeExtractor
from ..extractors.content_extractor import ContentExtractor
from ..extractors.property_extractor import PropertyExtractor
from ..extractors.metadata_extractor import MetadataExtractor

class WebNodeConverter:
    
    @staticmethod
    def _convert_to_node(raw_data: Dict[str, Any]) -> StandardUINode:
        """
        raw_data -> StandardUINode 변환
        
        해야 할 것:
        1. type 추출 (button, input, text, ...)
        2. content 추출 (텍스트)
        3. properties 추출 (모든 CSS 속성)
        4. metadata 추출 (디버깅용)
        """
        
        try:
            # 각 정보 추출
            node_type = TypeExtractor._extract_type(raw_data)
            content = ContentExtractor._extract_content(raw_data)
            properties = PropertyExtractor._extract_properties(raw_data)
            metadata = MetadataExtractor._extract_metadata(raw_data)
            
            # 클릭 가능한 버튼만 클릭
            is_interactive = WebNodeConverter._is_interactive(raw_data, node_type)
            properties['is_interactive'] = is_interactive
            
            # StandardUINode 생성
            return StandardUINode(
                id=metadata.get('xpath', ''),  # xpath를 id로 사용
                type=node_type,
                content=content,
                properties=properties,
                metadata=metadata
            )
        except Exception as e:
            # 변환 실패 시 None 반환
            print(f"Failed to convert element: {e}")
            return None
        
    @staticmethod
    def _is_interactive(raw_data: Dict[str, Any], node_type: str) -> bool:
        if node_type in ['button', 'link', 'input', 'select', 'checkbox', 'radio']:
            return True
        
        role = raw_data.get('role', '').lower()
        if role in ['button', 'link', 'menuitem', 'tab', 'option']:
            return True
        
        if raw_data.get('metadata', {}).get('has_onclick', False):
            return True
        
        """
        metadata = raw_data.get('metadata', {})
        if metadata.get('has_onclick', False):
            return True
        
        """
        
        properties = raw_data.get('properties', {})
        if properties.get('cursor') == 'pointer':
            return True
        
        return False