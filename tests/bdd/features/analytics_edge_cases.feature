# 分析仪表板 — 边界情况和高级报表
Feature: Analytics Edge Cases and Advanced Reports
  As a lab manager
  I want comprehensive analytics with edge case handling
  So that I can make data-driven decisions

  Background:
    Given I am authenticated as staff "manager1"

  # 空数据处理
  Scenario: Dashboard with no data
    Given no orders or inventory exist
    When I request the dashboard analytics
    Then all metrics should show zero or empty state
    And the response should indicate "no data" status

  Scenario: Spending report with no orders
    Given no orders exist in the system
    When I request spending by vendor report
    Then the report should show zero totals
    And the response should be valid JSON

  # 时间范围边界
  Scenario: Report with future date range
    When I request orders from 2030-01-01 to 2030-12-31
    Then the report should show zero results
    And no error should occur

  Scenario: Report with invalid date format
    When I request orders with date "invalid-date"
    Then I should receive a validation error
    And the error should specify correct date format

  Scenario: Report with start date after end date
    When I request orders from 2024-12-31 to 2024-01-01
    Then I should receive a validation error
    And the error should explain date order requirement

  # 大数据集
  Scenario: Report with large dataset
    Given 10000 orders exist in the system
    When I request the spending report
    Then the response should be paginated
    And query time should be under 5 seconds

  Scenario: Export large dataset to CSV
    Given 10000 products exist
    When I export products to CSV
    Then the file should be generated
    And the download should complete successfully

  # 并发请求
  Scenario: Concurrent analytics requests
    When 5 users request analytics simultaneously
    Then all requests should succeed
    And database connections should be properly managed

  # 聚合边界
  Scenario: Vendor with zero orders
    Given vendor "Empty Vendor" with no orders
    When I request vendor performance report
    Then "Empty Vendor" should appear with zero metrics

  Scenario: Product with no inventory movements
    Given product "Unused Product" with no movements
    When I request inventory turnover report
    Then the product should show zero turnover

  # 货币处理
  Scenario: Orders in different currencies
    Given orders in USD, EUR, and GBP exist
    When I request total spending report
    Then spending should be converted to base currency
    And currency conversion rates should be documented

  # 季节性分析
  Scenario: Month-over-month comparison
    Given orders spanning 12 months
    When I request monthly comparison
    Then each month should have separate totals
    And percentage changes should be calculated

  # 员工活动
  Scenario: Staff activity with no actions
    Given staff "newbie" has performed no actions
    When I request staff activity report
    Then "newbie" should appear with zero activities

  Scenario: Most active staff
    Given staff "poweruser" with 100 actions
    And staff "regular" with 50 actions
    When I request staff leaderboard
    Then "poweruser" should rank first
    And action counts should be displayed

  # 异常值
  Scenario: Detect spending outliers
    Given typical monthly spending is $5000
    And this month spending is $50000
    When I request anomaly report
    Then this month should be flagged as outlier
    And deviation percentage should be shown

  # 报表格式
  Scenario: Export analytics as PDF
    When I request analytics export in PDF format
    Then a valid PDF should be generated
    And the PDF should include charts

  Scenario: Export analytics as Excel
    When I request analytics export in Excel format
    Then a valid Excel file should be generated
    And multiple sheets should be included
