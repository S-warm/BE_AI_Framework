#src/normalizer/utils/image_analyzer/image_classifier.py

import statistics

class ImageClassifier:
    
    @staticmethod
    def classify_image_size(area: float, all_areas: list[float]) -> str:
        """
        IQR 기반 이미지 크기 3분류 (읽는 순서 결정용)
        
        인간은 큰 이미지를 먼저 인식하므로, 크기 기반으로 salience 순서 결정.
        IQR(Interquartile Range) 방식으로 데이터 기반 분류.
        
        - SMALL: Q1(25%) 이하 → 낮은 salience
        - MEDIUM: Q1~Q3(25%~75%) → 중간 salience  
        - LARGE: Q3(75%) 이상 → 높은 salience
        
        Args:
            area: 분류할 이미지의 면적 (width × height)
            all_areas: 페이지 내 모든 이미지의 면적 리스트
        
        Returns:
            'SMALL' | 'MEDIUM' | 'LARGE'
        
        Raises:
            ValueError: all_areas가 빈 리스트일 때
        """
        
        # 엣지 케이스: 빈 리스트
        if not all_areas:
            raise ValueError("all_areas cannot be empty")

        # 엣지 케이스: 이미지 1개
        if len(all_areas) == 1:
            return 'MEDIUM'
        
        # 이미지 2개
        if len(all_areas) == 2:
            sorted_areas = sorted(all_areas)
            return 'SMALL' if area <= sorted_areas[0] else 'LARGE'

        # 이미지 3개
        if len(all_areas) == 3:
            sorted_areas = sorted(all_areas)
            if area <= sorted_areas[0]:
                return 'SMALL'
            elif area >= sorted_areas[2]:
                return 'LARGE'
            else:
                return 'MEDIUM'
        
        # 정상 케이스: 이미지 4개 이상 → IQR 사용
        quartiles = statistics.quantiles(all_areas, n=4)
        q1 = quartiles[0]  # 25th percentile
        q3 = quartiles[2]  # 75th percentile
        
        if area <= q1:
            return 'SMALL'
        elif area >= q3:
            return 'LARGE'
        else:
            return 'MEDIUM'