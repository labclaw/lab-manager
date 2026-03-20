# 供应商管理 — 边界情况和高级场景
Feature: Vendors Edge Cases and Advanced Scenarios
  As a lab manager
  I want to handle complex vendor scenarios
  So that vendor relationships are well-managed

  Background:
    Given I am authenticated as staff "admin1"

  # 供应商状态变更
  Scenario: Deactivate vendor with pending orders
    Given vendor "Old Vendor" with 3 pending orders
    When I deactivate the vendor
    Then pending orders should remain active
    And new orders should be blocked
    And a warning should be shown

  Scenario: Reactivate previously deactivated vendor
    Given deactivated vendor "Returning Vendor"
    When I reactivate the vendor
    Then the vendor should be active
    And order history should be preserved

  # 供应商合并
  Scenario: Merge vendor records
    Given vendor "Thermo" with 50 orders
    And vendor "Thermo Fisher" with 30 orders
    When I merge "Thermo" into "Thermo Fisher"
    Then "Thermo Fisher" should have 80 orders
    And "Thermo" should be marked as merged

  # 联系人管理
  Scenario: Multiple contacts per vendor
    Given vendor "Sigma-Aldrich"
    When I add sales contact "John" and technical contact "Jane"
    Then both contacts should be associated
    And I can designate primary contact

  Scenario: Contact information update
    Given vendor "Bio-Rad" with contact email "old@bio-rad.com"
    When I update contact email to "new@bio-rad.com"
    Then the email should be updated
    And contact history should be maintained

  # 支付条款
  Scenario: Negotiate payment terms
    Given vendor "Fisher Scientific" with Net-30 terms
    When I update terms to Net-45
    Then payment terms should reflect Net-45
    And term change history should be logged

  # 最小订单金额
  Scenario: Enforce minimum order amount
    Given vendor "Bulk Supplier" with $500 minimum order
    When I create an order for $300
    Then I should receive a warning about minimum order
    And the order should not be submitted

  # 运费规则
  Scenario: Calculate shipping based on order value
    Given vendor with free shipping threshold $100
    When I order $99 worth of products
    Then shipping cost should be applied
    When I order $100 worth of products
    Then shipping should be free

  # 供应商评分
  Scenario: Rate vendor performance
    Given vendor "ABC Supplies" with 10 orders
    When I rate delivery speed 4/5 and product quality 5/5
    Then vendor average rating should be 4.5
    And ratings should be visible on vendor profile

  # 合规文档
  Scenario: Track vendor compliance documents
    Given vendor "Chemical Co" requires ISO certification
    When I upload ISO certificate with expiry date
    Then compliance status should show compliant
    And I should be notified before expiry

  # 供应商目录
  Scenario: Import vendor catalog
    Given vendor "New Vendor" with catalog spreadsheet
    When I import the catalog
    Then products should be created
    And prices should be linked to vendor

  # 多仓库
  Scenario: Vendor with multiple shipping origins
    Given vendor "National Supplier" with warehouses in CA and MA
    When I order from MA address
    Then the MA warehouse should be preferred
    And shipping time should be estimated correctly
