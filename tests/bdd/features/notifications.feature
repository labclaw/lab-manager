# 通知系统 — 事件通知和订阅
Feature: Notifications and Event Subscriptions
  As a lab manager
  I want to receive notifications for important events
  So that I don't miss critical lab updates

  Background:
    Given I am authenticated as staff "user1"

  # 库存预警
  Scenario: Receive low stock notification
    Given I am subscribed to low stock alerts
    And product "Antibody-A" has quantity 5 with reorder level 10
    When the daily check runs
    Then I should receive a notification
    And notification should mention "Antibody-A"

  Scenario: Receive expiring product notification
    Given I am subscribed to expiration alerts
    And product "Enzyme" expires in 7 days
    When the expiration check runs
    Then I should receive a notification
    And notification should show expiration date

  # 订单状态
  Scenario: Receive order shipped notification
    Given I placed order "ORD-001"
    And I am subscribed to order updates
    When the order status changes to "shipped"
    Then I should receive a notification
    And notification should include tracking info

  Scenario: Receive order delivered notification
    Given order "ORD-001" is in transit
    When the order is marked delivered
    Then I should receive a notification
    And I can confirm receipt

  # 通知偏好
  Scenario: Set notification delivery method
    When I set delivery method to "email"
    Then notifications should be sent via email

  Scenario: Set notification frequency
    When I set frequency to "daily digest"
    Then I should receive one daily summary
    And not individual notifications

  # 批量通知
  Scenario: Bulk notification for multiple low stock items
    Given 5 products are below reorder level
    When the daily check runs
    Then I should receive a single summary
    And all 5 products should be listed

  # 通知历史
  Scenario: View notification history
    Given I received 10 notifications
    When I request notification history
    Then I should see all 10 notifications
    And they should be sorted by date
