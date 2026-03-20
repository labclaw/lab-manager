# 报表生成 — 底层数据报表
Feature: Report Generation and Export
  As a lab manager
  I want to generate various reports
  So that I can analyze lab operations

  Background:
    Given I am authenticated as staff "manager1"

  # 库存报表
  Scenario: Generate inventory status report
    Given products with various inventory levels
    When I generate inventory status report
    Then report should contain product names
    And quantities for each product
    And reorder indicators

  Scenario: Export inventory report to PDF
    When I export inventory report as PDF
    Then a PDF file should be generated
    And report should be printable

  # 订单报表
  Scenario: Generate order history report
    Given orders from multiple vendors
    When I generate order history report
    Then report should show orders by date
    And vendor information
    And total values

  Scenario: Filter orders by date range
    Given orders spanning 6 months
    When I request orders from 2024-01-01 to 2024-03-31
    Then only Q1 orders should be included

  # 支出报表
  Scenario: Generate spending by vendor report
    Given orders from 5 vendors
    When I generate spending report
    Then each vendor total should be calculated
    And vendors should be sorted by spending

  Scenario: Spending by category
    Given orders across product categories
    When I request spending by category
    Then category breakdown should be shown
    And totals per category

  # 预警报表
  Scenario: Generate expiring products report
    Given products expiring in 30 days
    When I generate expiring report
    Then products expiring within 30 days should be listed
    And expiration dates should be shown

  Scenario: Generate low stock report
    Given products below reorder level
    When I generate low stock report
    Then products below reorder level should be listed
    And current stock levels should be shown

  # 供应商报表
  Scenario: Generate vendor performance report
    Given vendors with order history
    When I generate vendor performance report
    Then delivery performance should be shown
    And quality metrics should be included

  # 导出格式
  Scenario: Export to Excel format
    When I export report as Excel
    Then Excel compatible format should be generated
    And formatting should be preserved

  Scenario: Export to CSV format
    When I export report as CSV
    Then CSV file should be downloadable
    And special characters should be escaped

  # 定制报表
  Scenario: Create custom report with selected columns
    When I create custom report selecting name and quantity
    Then only selected columns should be included
    And other columns should be excluded

  Scenario: Schedule recurring report
    When I schedule a weekly inventory report
    Then report should be scheduled
    And delivery method should be set
