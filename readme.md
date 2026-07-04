# Threadline

## Overview
Threadline is a lightweight campus laundry request, payment, and tracking app built entirely with the Python standard library. It is designed for students and local laundry providers to manage requests, prioritize orders, apply discounts for shared pickup locations, and track order progress visually.

## Product Vision
Threadline aims to simplify the laundry workflow on campus by bringing visibility and control to both students and providers. Students can submit requests, choose priority handling, and pay once services are accepted. Providers can accept requests, update progress through stages, add common drop points, and confirm payment receipts.

## Key Features
- Student request creation with description, priority option, and shared pickup location discount
- Real-time order pricing calculation with base price, priority fee, and location-based discount
- Provider dashboard for accepting new requests and tracking accepted work
- Order progress states: requested → accepted → in progress → ready for pickup → completed
- Payment workflow: unpaid → paid → received
- Shared pickup location management for discount incentives
- Simple single-file Python app with no extra dependencies

## User Roles
- Student
  - Create laundry requests
  - Choose optional priority handling
  - Select shared pickup/dropoff location for a discount
  - View current request status and pay once accepted

- Provider
  - Review incoming laundry requests
  - Accept requests and assign provider name
  - Update request status as work progresses
  - Add and manage shared pickup locations with discounts
  - Confirm received payments

## Tech Stack
- Python 3
- Standard library only
  - `http.server` for the web interface
  - `sqlite3` for persistent request and location data
  - `html`, `urllib.parse`, `datetime` for request handling and rendering

## Architecture
- `app.py` contains the full application
- SQLite database file: `threadline.db`
- Two primary user flows:
  - Student flow: `/student`
  - Provider flow: `/provider`
- Status workflow managed by `STATUS_STAGES` with a visual clothesline progress tracker

## Pricing Rules
- Base price per request: `₹150`
- Priority fee: `₹75`
- Pickup location discount: variable per location
- Total price = `base price + priority fee - discount`

## Setup & Run
1. Ensure Python 3 is installed.
2. Open a terminal in the project folder.
3. Run the app:
   ```bash
   python app.py
   ```
4. Open the browser at:
   ```
   http://localhost:8000
   ```

## Database
- `locations` table stores shared pickup locations and discount amounts
- `requests` table stores laundry requests with fields including:
  - `student_name`
  - `description`
  - `priority`
  - `location_id`
  - `base_price`
  - `priority_fee`
  - `discount`
  - `total_price`
  - `status`
  - `payment_status`
  - `provider_name`
  - `created_at`

## Product Manager Notes
- This app is a strong portfolio example for campus services because it demonstrates:
  - end-to-end user journeys for two user roles
  - pricing and discount logic
  - workflow state management
  - real-time visibility into order progress
  - clean UI experience without external dependencies
- The product model emphasizes value for students (convenience, flexible pickup, priority service) and providers (task acceptance, order tracking, payment confirmation).

## Future Enhancements
- Add user authentication and role-based login
- Introduce request search and filtering
- Enable notifications for status updates
- Add analytics for provider performance and request volumes
- Improve UI/UX with a dedicated front-end framework

## Contact
For more details or product context, review `app.py` or demo the app locally.
