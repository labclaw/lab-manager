# 统一搜索界面 — 全局搜索栏、分组结果、自动补全
Feature: Unified Search UI
  As a lab scientist at Shen Lab
  I want a fast search that finds anything across the system
  So that I can quickly locate documents, products, vendors, and orders

  Background:
    Given I am logged in as a scientist

  # 导航栏搜索入口
  Scenario: Search bar is always visible in navbar
    When I am on any view
    Then I should see a search input in the navbar
    And the search input should have placeholder text "Search..."

  # 搜索触发导航
  Scenario: Typing in navbar search navigates to search view
    Given I am on the dashboard view
    When I type "antibody" in the navbar search
    And I press Enter
    Then the URL hash should be "#/search?q=antibody"
    And the search view should be visible

  # 搜索结果分组
  Scenario: Search results are grouped by type
    Given products "Anti-GFP Antibody" and "GFP Protein" exist
    And a vendor "GFP Biotech" exists
    When I search for "GFP"
    Then results should be grouped under "Products" and "Vendors" headings
    And the product section should show matching products
    And the vendor section should show "GFP Biotech"

  # 自动补全下拉
  Scenario: Autocomplete suggestions appear while typing
    Given products "Sodium Chloride", "Sodium Hydroxide" exist and are indexed
    When I type "sodi" in the search input
    Then an autocomplete dropdown should appear
    And it should show suggestions containing "Sodium"

  # 点击搜索结果
  Scenario: Clicking a search result navigates to detail
    Given a product search result exists
    When I click on a product result
    Then I should navigate to the relevant detail view

  # 无结果
  Scenario: No results shows empty state with suggestions
    When I search for "xyznonexistent123"
    Then I should see an empty state message "No results found"
    And I should see a suggestion like "Try a different search term"

  # 清空搜索
  Scenario: Clearing search input returns to previous view
    Given I searched for "antibody" and see results
    When I clear the search input
    And I press Enter
    Then the search results should clear

  # 搜索特殊字符
  Scenario: Search handles special characters safely
    When I search for "<script>alert(1)</script>"
    Then no JavaScript should execute
    And I should see 0 results or a safe error message
