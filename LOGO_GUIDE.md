# MCP Realtime Airbnb Assistant - 로고 가이드

## 📁 생성된 파일들

### 로고 파일
- `public/logo.svg` - 메인 로고 (200x60px)
- `public/favicon.svg` - 파비콘 (32x32px)
- `public/logo-preview.html` - 로고 미리보기 페이지
- `public/convert-favicon.html` - PNG 파비콘 생성 도구

### 설정 파일
- `.chainlit/config.toml` - Chainlit 설정에 로고 적용

## 🎨 디자인 컨셉

### 메인 로고 구성 요소
1. **집 아이콘** 🏠 
   - Airbnb 숙박 서비스를 상징
   - Airbnb 브랜드 컬러 그라디언트 적용

2. **채팅 버블** 💬
   - AI 챗봇 기능 표현
   - 체크마크로 성공적인 소통 의미

3. **실시간 웨이브** 🎵
   - 음성 대화 기능 강조
   - 애니메이션으로 실시간성 표현

4. **MCP 인디케이터** 🔗
   - Model Context Protocol 연결 상태
   - 3개의 점이 순차적으로 활성화

### 컬러 팔레트
- **주요 색상**: #FF5A5F (Airbnb 핑크) ~ #D70466 (진한 핑크)
- **보조 색상**: #00D4AA (민트 그린), #3498DB (파랑), #E74C3C (빨강), #2ECC71 (초록)
- **텍스트**: #2C3E50 (진한 회색), #7F8C8D (연한 회색)

## 🚀 사용법

### 1. 웹사이트에서 확인
```bash
# 미리보기 서버 실행
python -m http.server 8080 --directory public

# 브라우저에서 접속
http://localhost:8080/logo-preview.html
```

### 2. Chainlit에서 확인
```bash
# Chainlit 애플리케이션 실행
chainlit run chat.py

# 브라우저에서 확인 (로고가 헤더에 표시됨)
http://localhost:8000
```

### 3. PNG 파비콘 생성 (필요시)
1. `public/convert-favicon.html` 파일을 브라우저에서 열기
2. 자동으로 `favicon.png` 파일 다운로드

## 📱 반응형 디자인

- **SVG 형식**: 모든 화면 크기에서 선명하게 표시
- **벡터 그래픽**: 확대/축소 시 품질 손실 없음
- **애니메이션**: CSS 애니메이션으로 실시간 효과

## 🔧 커스터마이징

### 색상 변경
```css
/* CSS에서 색상 변경 가능 */
.logo svg [fill="#FF5A5F"] {
    fill: #새로운색상;
}
```

### 애니메이션 조정
```css
/* 애니메이션 속도 조절 */
.logo svg animate {
    dur: 2s; /* 기본 1s에서 2s로 변경 */
}
```

## 📋 파일 구조
```
public/
├── logo.svg              # 메인 로고
├── favicon.svg            # SVG 파비콘
├── logo-preview.html      # 미리보기 페이지
└── convert-favicon.html   # PNG 변환 도구

.chainlit/
└── config.toml           # 로고 설정 적용됨
```

## 💡 추가 아이디어

1. **다크모드 버전**: 어두운 배경용 로고 변형
2. **애니메이션 강화**: 마우스 호버 효과 추가
3. **브랜딩 확장**: 명함, 문서 템플릿 등에 활용
4. **소셜 미디어**: 프로필 이미지, 커버 이미지 버전

---

**제작 정보**
- 디자인: MCP Realtime Airbnb Assistant 전용
- 형식: SVG (벡터)
- 호환성: 모든 모던 브라우저
- 라이선스: 프로젝트 내부 사용