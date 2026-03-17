# 告警与监控 — 过期预警、低库存、待审核
Feature: Alerts and Monitoring
  As a lab manager at Shen Lab
  I want automatic alerts for expiring reagents, low stock, and pending reviews
  So that nothing falls through the cracks

  # 检测过期试剂
  Scenario: Detect expiring reagents
    Given an inventory item expiring in 7 days
    When I run the alert check
    Then an expiry alert should be created
    And the alert type should be "expiring_soon"

  # 检测低库存
  Scenario: Detect low stock
    Given a product with min_stock_level 10
    And inventory total quantity is 3
    When I run the alert check
    Then a low stock alert should be created
    And the alert type should be "low_stock"

  # 告警列表
  Scenario: List active alerts
    Given 3 active alerts exist
    And 2 resolved alerts exist
    When I list active alerts
    Then I should see 3 alerts
    And all alerts should be unresolved

  # 确认告警
  Scenario: Acknowledge an alert
    Given an active alert exists
    When I acknowledge the alert
    Then the alert should be acknowledged

  # 解决告警
  Scenario: Resolve an alert
    Given an active alert exists
    When I resolve the alert
    Then the alert should be resolved

  # 告警汇总
  Scenario: Alert summary counts
    Given 5 inventory items expiring soon
    And 3 products with low stock
    And 2 documents pending review
    When I request the alert summary
    Then the summary should show 10 total active alerts
    And the summary should break down by type
