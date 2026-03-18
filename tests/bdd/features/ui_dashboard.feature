# 仪表板 — 增强版：统计、警报、最近订单
Feature: Enhanced Dashboard
  As a lab scientist at Shen Lab
  I want to see an overview of lab status at a glance
  So that I know about low stock, expiring items, and pending reviews immediately

  Background:
    Given I am logged in as a scientist
    And I am on the dashboard view

  # 统计卡片
  @wip
  Scenario: Dashboard shows stat cards with live data
    Given 50 documents exist with various statuses
    And 10 vendors exist
    And 25 orders exist
    When the dashboard loads
    Then I should see a stat card "Total Documents" with value "50"
    And I should see a stat card "Vendors" with a numeric value
    And I should see a stat card "Orders Created" with a numeric value

  # 低库存警报横幅
  @wip
  Scenario: Dashboard shows alert banner for low stock
    Given 3 inventory items are below reorder level
    When the dashboard loads
    Then I should see an alert banner with text containing "low stock"
    And the alert banner should show count "3"

  # 即将过期警报
  @wip
  Scenario: Dashboard shows expiring items alert
    Given 5 inventory items expire within 30 days
    When the dashboard loads
    Then I should see an alert section for expiring items
    And it should show "5" items expiring soon

  # 待审核提示
  @wip
  Scenario: Dashboard shows pending review count
    Given 12 documents have status "needs_review"
    When the dashboard loads
    Then I should see a stat card "Needs Review" with value "12"
    And the "Needs Review" card should have a warning color

  # 供应商图表
  @wip
  Scenario: Dashboard shows top vendors chart
    Given documents from 5 different vendors exist
    When the dashboard loads
    Then I should see a "Top Vendors" section
    And it should show horizontal bars for each vendor

  # 空数据库仪表板
  @wip
  Scenario: Dashboard handles empty database gracefully
    Given the database is empty
    When the dashboard loads
    Then I should see stat cards with value "0"
    And I should not see any error messages
    And the vendor chart should show an empty state
