# Ente Naadu Project Context & Technical Architecture

## Overview
**Ente Naadu (എന്റെ നാട്)** is an open-source, grassroots village commerce and citizen service platform for local panchayats in Kerala. It combines hyperlocal shop discovery, direct ordering, service appointments, citizen grievance redressing, community directory, and peer-to-peer social interaction with zero hosting cost overhead.

---

## Category-Based Rating & Review System

### 1. Architecture & Design Principles
The Category-Based Rating System extends the platform's trust and moderation layer by transitioning from basic 1-to-5 star shop ratings to category-tailored, multi-criteria evaluations:
- **Dynamic Criteria Resolution**: Shop category overrides > Business type defaults > Built-in constants (`DEFAULT_RATING_CRITERIA`).
- **Strict Non-Compounded Overall Rating**: The overall average score (`overall_average_rating`) is strictly derived from verified overall reviews (`Review.rating`) rather than the average of criteria averages, avoiding arithmetic distortion.
- **Historical Fidelity & Snapshots**: When criteria are modified, disabled, or removed in the future, older reviews retain their historical criteria names and slugs (`criterion_name`, `criterion_name_ml`, `criterion_slug`).
- **Verified Interaction Gating**: Only customers with completed orders or completed bookings can rate a shop. Pending, confirmed, or cancelled transactions are rejected.
- **Single Review & Self-Review Protection**: One review per user per shop (`unique_together = ('shop', 'user')`). Shop owners cannot review their own shops.

---

### 2. Data Models (`backend/apps/shops/models.py`)

#### `RatingCriterion`
Configurable rating criteria per shop category or business type:
- `category` (FK `ShopCategory`, optional override)
- `business_type` (CharField, `ShopCategory.BusinessType`)
- `name` (CharField, English label)
- `name_ml` (CharField, Malayalam label)
- `slug` (SlugField, unique per business type / category)
- `is_required` (BooleanField)
- `order` (PositiveSmallIntegerField, sort order)
- `is_active` (BooleanField, active toggle)
- `created_at` / `updated_at` (DateTime)

#### `Review` (Enhanced)
Core review linked to shop and verified transaction:
- `shop` (FK `Shop`)
- `user` (FK `User`)
- `order` (FK `Order`, null=True, blank=True)
- `booking` (FK `Booking`, null=True, blank=True)
- `rating` (PositiveSmallIntegerField, 1–5 validator)
- `comment` (TextField, general written review)
- `created_at` / `updated_at` (DateTime)
- `is_verified_buyer` (property checking completed order/booking)
- Meta: `unique_together = ('shop', 'user')`

#### `ReviewCriterionRating`
Multi-dimensional ratings for individual criteria:
- `review` (FK `Review`, cascade)
- `criterion` (FK `RatingCriterion`, set_null on delete)
- `criterion_name` (CharField, snapshot)
- `criterion_name_ml` (CharField, snapshot)
- `criterion_slug` (CharField, db_index=True)
- `rating` (PositiveSmallIntegerField, 1–5 validator)
- `feedback` (TextField, optional written feedback per criterion)
- `created_at` (DateTime)
- Meta: `unique_together = ('review', 'criterion_slug')`

---

### 3. Business Category Dynamic Criteria

| Category / Business Type | Key Criteria | Malayalam Translation |
| :--- | :--- | :--- |
| **General Shop** (`general`) | Cleanliness, Pricing, Quality, Service | ശുചിത്വം, വിലനിലവാരം, ഗുണനിലവാരം, ഉപഭോക്തൃ സേവനം |
| **Beauty Parlour / Salon** (`beauty_parlour`) | Hygiene, Service Quality, Staff Behavior, Ambience, Value for Money | ശുചിത്വം, സേവന മികവ്, ജീവനക്കാരുടെ പെരുമാറ്റം, അന്തരീക്ഷം, ന്യായമായ നിരക്ക് |
| **Repair Shop** (`repair`) | Diagnostic Accuracy, Repair Quality, Pricing Transparency, Turnaround Time | തകരാർ കണ്ടെത്തൽ, റിപ്പയർ ഗുണനിലവാരം, വ്യക്തമായ നിരക്കുകൾ, വേഗത്തിലുള്ള സേവനം |
| **Restaurant & Cafe** (`restaurant`) | Food Taste, Hygiene, Service Speed, Packaging, Value for Money | ഭക്ഷണ രുചി, ശുചിത്വം, വിളമ്പൽ വേഗത, പാക്കിംഗ് നിലവാരം, ന്യായമായ നിരക്ക് |
| **Other Service Businesses** (`other_service`) | Service Quality, Punctuality, Communication, Pricing | സേവന മികവ്, കൃത്യനിഷ്ഠ, ആശയവിനിമയം, ന്യായമായ നിരക്ക് |

---

### 4. REST API Endpoints

| Method | Endpoint | Description | Auth Required |
| :--- | :--- | :--- | :--- |
| `GET` | `/api/v1/shops/shops/<id>/rating-summary/` | Overall average, total verified reviews count, 5-to-1 star distribution (counts & percentages), criteria averages, and recent reviews. | No |
| `GET` | `/api/v1/shops/shops/<id>/rating-criteria/` | Active criteria list for the shop's category. | No |
| `GET` | `/api/v1/shops/shops/<id>/can-review/` | Evaluates if authenticated user can review: completed order/booking status, existing review check, ownership check. | Yes |
| `POST` | `/api/v1/shops/reviews/` | Submit verified review with overall rating, optional comment, order/booking ID, and `criteria_ratings` array. | Yes |
| `GET` | `/api/v1/shops/reviews/my_review/?shop_id=<id>` | Returns authenticated user's existing review for the shop. | Yes |
| `GET` / `POST` | `/api/v1/shops/rating-criteria/` | Admin CRUD for dynamic criteria per category. | Yes (Admin) |

---

### 5. Web Portal Routes & Templates

- **Shop Detail** (`/shops/<id>/`):
  - Card analytics grid: Large overall rating score, star distribution bars, category criteria progress bars.
  - Recent reviews listing with criteria breakdown pill badges.
  - Dynamic review modal with 1–5 stars per criterion, optional feedback per criterion, overall stars, and general review.
- **User Dashboard** (`/dashboard/user/`):
  - "⭐ റേറ്റ് ചെയ്യുക" action button on completed orders and completed bookings.
  - "✓ റേറ്റിംഗ് നൽകി" indicator for already-reviewed purchases.
- **Order Detail** (`/orders/<id>/`):
  - Verified review status and prompt for completed orders.
- **Form Submission** (`/shops/<id>/review/`):
  - Handles POST submissions with CSRF verification, atomic database transaction, and Malayalam flash notifications.

---

### 6. Flutter Mobile App Integration

- **`mobile/lib/core/api_service.dart`**:
  - `fetchShopRatingSummary(shopId)`
  - `fetchShopRatingCriteria(shopId)`
  - `checkCanReviewShop(shopId)`
  - `submitReview(shopId, rating, comment, orderId, bookingId, criteriaRatings)`
- **`mobile/lib/screens/shop_detail_screen.dart`**:
  - Renders rating summary analytics card, 5–1 star distribution, category criteria bars, and recent reviews.
  - Interactive `_showReviewDialog()` dynamic rating dialog with live criteria fetching and multi-criteria feedback.
- **`mobile/lib/screens/orders_screen.dart`** & **`mobile/lib/screens/bookings_screen.dart`**:
  - "⭐ റേറ്റ് ചെയ്യുക" action buttons on completed orders and bookings linking directly to the rating flow.

---

### 7. Verification & Automated Test Coverage

The test suite in `backend/apps/shops/tests.py` validates:
- Dynamic criteria resolution for all 5 business categories.
- Completed order-based and booking-based reviews.
- Strict rejection of pending, confirmed, or cancelled orders/bookings.
- Strict rejection of visitors without completed purchases.
- Prevention of shop owners reviewing their own businesses.
- 1–5 star boundary enforcement for overall and criteria ratings.
- Prevention of duplicate reviews per shop.
- Mathematical accuracy of non-compounded overall rating and criteria averages.
- Future category support and criteria snapshot preservation.
- Web portal form submission and redirects.
