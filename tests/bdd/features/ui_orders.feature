# 订单管理界面 — 查看、筛选、收货、项目管理
Feature: Order Management UI
  As a lab manager at Shen Lab
  I want to view and manage purchase orders through the web interface
  So that I can track deliveries, receive shipments, and see order history

  Background:
    Given I am logged in as a scientist
    And I am on the orders view

  # 订单列表
  Scenario: Orders list shows key fields
    Given 20 orders exist from various vendors
    When the orders view loads
    Then I should see a table with columns "PO#", "Vendor", "Date", "Status", "Items"
    And each row should show the PO number and vendor name

  # 按供应商筛选
  Scenario: Filter orders by vendor
    Given orders from "Fisher Scientific" and "Sigma-Aldrich" exist
    When I select vendor filter "Fisher Scientific"
    Then only orders from "Fisher Scientific" should be displayed

  # 按状态筛选
  Scenario: Filter orders by status
    Given orders with statuses "pending", "received", "cancelled" exist
    When I select status filter "pending"
    Then only orders with status "pending" should be displayed

  # 按日期范围筛选
  Scenario: Filter orders by date range
    Given orders from January and March 2026 exist
    When I set date range from "2026-03-01" to "2026-03-31"
    Then only March orders should be displayed

  # 订单详情
  Scenario: Click order row opens detail panel with items
    Given an order "PO-2026-100" with 3 items exists
    When I click on the order row for "PO-2026-100"
    Then the detail panel should open
    And it should show order info: PO number, vendor, dates, status
    And it should show a line items table with 3 rows
    And each item should show catalog number, description, quantity, unit

  # 收货操作
  Scenario: Receive a pending order
    Given a pending order "PO-2026-200" with 2 items exists
    And products matching each order item exist
    When I open the order detail
    And I click "Mark Received"
    Then a confirmation modal should appear "Receive this order?"
    When I confirm
    Then I should see a success toast "Order received"
    And the order status should change to "received"
    And inventory items should be created

  # 已收货订单无收货按钮
  Scenario: Received orders do not show receive button
    Given a received order exists
    When I open the order detail
    Then I should not see a "Mark Received" button
    And I should see the status badge "received"
    And I should see who received it and when

  # 订单详情中的项目
  Scenario: Order items show full detail
    Given an order with items including lot numbers and units
    When I open the order detail
    Then each line item should display:
      | field          |
      | catalog_number |
      | description    |
      | quantity       |
      | unit           |
      | lot_number     |

  # 搜索订单
  Scenario: Search orders by PO number
    Given an order with po_number "PO-RUSH-999" exists
    When I type "RUSH" in the orders search input
    Then the order "PO-RUSH-999" should be visible in the list

  # 空订单列表
  Scenario: Empty orders shows helpful message
    Given no orders exist
    When the orders view loads
    Then I should see an empty state message "No orders found"

  # 翻页
  Scenario: Orders pagination works
    Given 60 orders exist
    When the orders view loads
    Then I should see "Page 1 of 2"
    When I click "Next"
    Then I should see "Page 2 of 2"
    And different orders should be displayed

  # 订单不存在
  Scenario: Navigate to non-existent order shows not found
    When I navigate to "#/orders/99999"
    Then I should see a "Not Found" message in the detail area
