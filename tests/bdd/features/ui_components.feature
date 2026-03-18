# 共享组件 — 表格、分页、加载状态、错误状态、模态框、吐司通知
Feature: Shared UI Components
  As a lab scientist at Shen Lab
  I want consistent, reliable UI components across all views
  So that the interface is predictable and easy to use

  Background:
    Given I am logged in as a scientist

  # 表格排序
  @wip
  Scenario: Table columns are sortable by clicking headers
    Given I am on the documents view with 10 documents
    When I click the "Vendor" column header
    Then documents should be sorted by vendor name ascending
    When I click the "Vendor" column header again
    Then documents should be sorted by vendor name descending

  # 加载状态
  @wip
  Scenario: Loading state shows while data is fetching
    Given I am on the inventory view
    When the API request is in progress
    Then I should see a loading indicator
    And the table should not show stale data

  # 错误状态
  @wip
  Scenario: Error state shows when API call fails
    Given the API is unreachable
    When I navigate to the documents view
    Then I should see an error toast "Network error"

  # 空状态
  @wip
  Scenario: Empty state shows when no data exists
    Given no documents exist
    When I navigate to the documents view
    Then I should see an empty state with message "No documents found"

  # 吐司通知自动消失
  @wip
  Scenario: Toast notifications disappear after timeout
    Given I perform an action that triggers a success toast
    Then I should see the toast message
    And the toast should automatically disappear after 5 seconds

  # 模态框遮罩点击关闭
  @wip
  Scenario: Modal closes when clicking outside
    Given a confirmation modal is open
    When I click the overlay outside the modal
    Then the modal should close

  # 认证过期自动重定向
  @wip
  Scenario: Session expiry redirects to login
    Given my session has expired
    When I try to load any view
    Then I should be redirected to the login screen
    And I should see a toast "Session expired. Please sign in again."

  # 响应式布局
  @wip
  Scenario: Mobile layout adapts gracefully
    Given I am on a 375px wide viewport
    When I view the documents list
    Then the table should hide non-essential columns
    And the detail panel should take full width
    And navigation should still be usable
