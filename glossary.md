# Olist 비즈니스 용어 사전

회사 안에서 쓰는 지표와 용어의 공식 정의입니다. 질문에 아래 용어가 나오면 반드시 이 정의대로 계산합니다.

## 공통 규칙
- **분석 기준일**: 2018-08-31. 데이터의 마지막 정상 월이 2018년 8월입니다.
- **최근 3개월**: 구매 시점 기준 2018-06-01 00:00:00 이상, 2018-09-01 00:00:00 미만.
- **기간 기준**: 연도, 월, 분기 등 기간 조건은 모두 구매 시점(`orders.order_purchase_timestamp`) 기준입니다.
- **고객**: 사람 기준으로 셉니다. `customers.customer_unique_id`가 같으면 한 명입니다. (`customer_id`는 주문마다 새로 생기는 ID입니다.)
- **카테고리**: 영어 이름(`category_translation.product_category_name_english`)을 씁니다.
- **리뷰 건수**: `order_reviews`의 행 수 기준입니다.

## 주문
- **유효 주문**: 주문 상태(`order_status`)가 `canceled`, `unavailable`이 아닌 주문.
- **완료 주문**: 주문 상태가 `delivered`인 주문.

## 매출 지표
- **GMV**: 완료 주문에 포함된 상품의 상품 가격(`price`)과 배송비(`freight_value`)를 모두 더한 금액.
- **순매출**: 완료 주문에 포함된 상품의 상품 가격(`price`) 합계. 배송비는 뺍니다.
- **객단가(AOV)**: GMV ÷ 완료 주문 수.

## 고객
- **재구매 고객**: 유효 주문이 2건 이상인 고객.
- **VIP 고객**: 유효 주문의 결제 금액(`order_payments.payment_value`) 합계가 1,000 이상인 고객.

## 판매자
- **활성 판매자**: 최근 3개월 안에 구매된 유효 주문에서 상품을 1개 이상 판매한 판매자.
- **우수 판매자**: 최근 3개월 GMV가 10,000 이상인 판매자.

## 리뷰
- **불만 리뷰**: 리뷰 점수(`review_score`)가 2점 이하인 리뷰.
- **만족 리뷰**: 리뷰 점수가 4점 이상인 리뷰.
- **리뷰 순추천 지수**: (만족 리뷰 비율 − 불만 리뷰 비율) × 100. 비율은 전체 리뷰 건수 대비입니다.

## 배송
- **지연 배송**: 완료 주문 중 고객 도착 날짜(`order_delivered_customer_date`의 날짜 부분)가 예상 배송 날짜(`order_estimated_delivery_date`의 날짜 부분)보다 늦은 주문. 시각은 보지 않고 날짜만 비교합니다. 고객 도착 날짜가 없는 주문은 계산에서 뺍니다.
- **배송 리드타임**: 판매자가 택배사에 넘긴 시점(`order_delivered_carrier_date`)부터 고객 도착 시점(`order_delivered_customer_date`)까지의 일수. 완료 주문 중 두 값이 모두 있는 주문만 계산합니다.

## 상품
- **대형 상품**: 무게(`product_weight_g`)가 10kg 이상이거나, 가로·세로·높이(`product_length_cm`, `product_width_cm`, `product_height_cm`) 중 가장 긴 변이 100cm 이상인 상품.

## 결제
- **할부 결제**: 결제 방식이 `credit_card`이고 할부 개월 수(`payment_installments`)가 2 이상인 결제.
- **할부 결제 비율**: 할부 결제 건수 ÷ 신용카드 결제 건수 × 100.

## 지역
- **핵심 지역**: 고객이 사는 주(`customers.customer_state`)가 SP, RJ, MG인 경우.
