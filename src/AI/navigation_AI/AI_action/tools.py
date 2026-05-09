"""
OpenAI Function Calling Tool 정의
"""

NAVIGATION_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "click_element",
            "description": "웹페이지 요소 클릭. StandardUINode.node_id로 요소 지정",
            "parameters": {
                "type": "object",
                "properties": {
                    "node_id": {
                        "type": "string",
                        "description": "클릭할 요소의 node_id (xpath 기반 고유 ID)"
                    },
                    "reasoning": {
                        "type": "string",
                        "description": "왜 이 요소를 클릭하는지 이유"
                    }
                },
                "required": ["node_id", "reasoning"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "fill_input",
            "description": "입력창에 텍스트 입력",
            "parameters": {
                "type": "object",
                "properties": {
                    "node_id": {
                        "type": "string",
                        "description": "입력창의 node_id"
                    },
                    "text": {
                        "type": "string",
                        "description": "입력할 텍스트"
                    }
                },
                "required": ["node_id", "text"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "declare_success",
            "description": "최종 목표 달성 선언. 목표 페이지/요소에 도달했을 때 호출",
            "parameters": {
                "type": "object",
                "properties": {
                    "reasoning": {
                        "type": "string",
                        "description": "목표 달성 이유"
                    }
                },
                "required": ["reasoning"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "declare_failure",
            "description": "목표 달성 불가 선언. 더 이상 진행할 수 없을 때",
            "parameters": {
                "type": "object",
                "properties": {
                    "reasoning": {
                        "type": "string",
                        "description": "실패 이유"
                    }
                },
                "required": ["reasoning"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "go_back",
            "description": "브라우저 뒤로가기. 잘못된 페이지에 갔을 때 사용",
            "parameters": {
                "type": "object",
                "properties": {
                    "reasoning": {
                        "type": "string",
                        "description": "왜 뒤로가기 하는지 이유"
                    }
                },
                "required": ["reasoning"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "upload_file",
            "description": "파일 업로드 input에 파일 선택. 회원가입, 프로필 사진 등에 사용",
            "parameters": {
                "type": "object",
                "properties": {
                    "node_id": {
                        "type": "string",
                        "description": "파일 input 요소의 node_id"
                    },
                    "file_path": {
                        "type": "string",
                        "description": "업로드할 파일 경로 (상대/절대 경로)"
                    }
                },
                "required": ["node_id", "file_path"]
            }
        }
    }
]