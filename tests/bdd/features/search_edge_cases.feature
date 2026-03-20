# 搜索与发现 — 边界情况和错误处理
Feature: Search Edge Cases and Error Handling
  As a lab scientist
  I want the search to handle edge cases gracefully
  So that I can trust the search results

  Background:
    Given I am authenticated as staff "scientist1"

  # 特殊字符处理
  Scenario: Search with special characters
    Given products "C57BL/6 Mouse", "HEK-293T Cells" exist and are indexed
    When I search for "C57BL/6"
    Then I should get results including "C57BL/6 Mouse"

  Scenario: Search with SQL injection attempt
    When I search for "'; DROP TABLE products; --"
    Then the search should be sanitized
    And no database error should occur

  Scenario: Search with XSS attempt
    When I search for "<script>alert('xss')</script>"
    Then the search should be sanitized
    And the response should not execute any script

  # Unicode 支持
  Scenario: Search with Chinese characters
    Given product "抗体 (Antibody)" exists and is indexed
    When I search for "抗体"
    Then I should get results including "抗体 (Antibody)"

  Scenario: Search with emoji
    Given product "Test Tube 🔬" exists and is indexed
    When I search for "🔬"
    Then I should get results if supported

  # 查询限制
  Scenario: Search query too long
    When I search for a 500 character query
    Then the search should be truncated or rejected gracefully

  Scenario: Search with minimum query length
    When I search for "a"
    Then I should receive a validation error
    And the error should indicate minimum query length

  # 索引状态
  Scenario: Search when index is empty
    Given no documents are indexed
    When I search for "anything"
    Then I should get 0 results
    And the response should indicate empty index

  Scenario: Search when Meilisearch is unavailable
    Given Meilisearch service is down
    When I search for "test"
    Then I should receive an error response
    And the error should indicate search service unavailable

  # 分页边界
  Scenario: Search results pagination beyond available
    Given 10 products matching "reagent" exist
    When I search for "reagent" with page 100
    Then I should get 0 results
    And the response should indicate last page

  Scenario: Search with negative page number
    When I search for "test" with page -1
    Then I should receive a validation error

  # 排序和过滤
  Scenario: Search with invalid sort field
    When I search for "test" sorted by "invalid_field"
    Then the sort should fall back to default relevance
    And I should receive a validation error

  # 并发搜索
  Scenario: Concurrent search requests
    Given search index is stable
    When I make 10 concurrent search requests
    Then all requests should return valid results
    And no race conditions should occur

  # 模糊匹配边界
  Scenario: Fuzzy match with typos
    Given product "Phosphate Buffered Saline" exists
    When I search for "Phosphate Bffered Saline"
    Then I should get results for "Phosphate Buffered Saline"

  Scenario: Exact match vs fuzzy match preference
    Given product "GFP" exists
    And product "GFP Antibody" exists
    When I search for "GFP"
    Then exact match "GFP" should rank higher than "GFP Antibody"
