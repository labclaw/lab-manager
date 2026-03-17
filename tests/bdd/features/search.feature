# 搜索与发现 — 全文搜索和自动补全
Feature: Search and Discovery
  As a lab scientist at Shen Lab
  I want to quickly find products, vendors, and orders
  So that I can locate what I need without browsing through tables

  # 跨索引搜索
  Scenario: Search across all indexes
    Given the following data is indexed:
      | type    | name                        |
      | vendor  | Thermo Fisher Scientific    |
      | product | Trypsin-EDTA Solution       |
      | product | Trypan Blue Stain           |
    When I search for "Tryp"
    Then I should get results from "products" index
    And the results should include "Trypsin-EDTA Solution"

  # 按供应商搜索
  Scenario: Search for a specific vendor
    Given a vendor "Sigma-Aldrich" exists and is indexed
    When I search for "sigma" in index "vendors"
    Then I should get 1 result
    And the result name should be "Sigma-Aldrich"

  # 自动补全
  Scenario: Autocomplete suggestions
    Given products "Sodium Chloride", "Sodium Hydroxide", "Sodium Bicarbonate" exist and are indexed
    When I request suggestions for "sodium"
    Then I should get at least 3 suggestions
    And all suggestions should be of type "product"

  # 空结果
  Scenario: Search returns empty for unknown term
    When I search for "xyznonexistent123"
    Then I should get 0 total results
