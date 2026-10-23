# dang2_lab 자동 게시

인스타그램 [@dang2_lab](https://www.instagram.com/dang2_lab/) 카드뉴스를 만들고 예약 시간에 올리는 저장소예요.

## 어떻게 돌아가나요

1. `posts/<날짜-시간-주제>/post.json` 에 게시물(슬라이드 문구, 사진, 캡션, 게시 시간)이 들어 있어요.
2. 새 `post.json` 이 올라오면 **render cards** 작업이 카드 이미지(`1.jpg`, `2.jpg` …)를 만들어 저장해요.
3. **publish to instagram** 작업이 30분마다 돌면서, 게시 시간이 지난 게시물을 Instagram API로 올려요.
   올리고 나면 그 폴더에 `posted.json` 이 생겨요. 한 번 올린 뒤 3시간은 다음 게시물을 올리지 않아요.
   - 정각에 딱 맞춰 올라가지 않도록 올리기 전 1~12분 무작위로 기다려요.
   - 게시 시간보다 6시간 넘게 밀린 게시물은 몰아서 올리지 않고, 예약된 마지막 게시물 다음 시간대(12:30/20:30)로 자동으로 옮겨요.
4. **refresh instagram token** 작업이 매주 월요일 Instagram 토큰을 연장해서 `IG_TOKEN` 을 새 토큰으로 바꿔요.

## 게시를 멈추고 싶을 때

- 특정 게시물만 빼기: 그 폴더를 지우거나 `post.json` 의 `time` 을 미래로 바꿔요.
- 전부 멈추기: **Actions → publish to instagram → ⋯ → Disable workflow**

## 필요한 비밀값 (Settings → Secrets and variables → Actions)

| 이름 | 내용 |
|---|---|
| `IG_TOKEN` | Meta 앱에서 만든 Instagram 액세스 토큰 (매주 자동 연장돼요) |
| `GH_PAT` | `IG_TOKEN` 자동 연장용 GitHub 개인 액세스 토큰 (이 저장소, Secrets 읽기·쓰기 권한) |
| `PEXELS_KEY` | (선택) Pexels API 키. 사진을 검색어로 고를 때만 필요해요 |

사진: [Pexels](https://www.pexels.com) 무료 이미지
