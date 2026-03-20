# AI 问答助手 — 自然语言查询实验室数据
Feature: AI Ask Assistant
  As a lab scientist
  I want to ask questions in natural language about lab data
  So that I can get insights without writing complex queries

  Background:
    Given I am authenticated as staff "scientist1"

  # 基础问答
  Scenario: Ask about total spending
    Given vendors "Thermo Fisher", "Sigma-Aldrich" exist
    And orders exist with total value $5000
    When I ask "What is our total spending?"
    Then I should receive a response with spending information
    And the response should be in markdown format

  Scenario: Ask about vendor performance
    Given vendor "Thermo Fisher" with 10 delivered orders
    And vendor "Sigma-Aldrich" with 5 delayed orders
    When I ask "Which vendor has the best delivery record?"
    Then I should receive a response mentioning "Thermo Fisher"
    And the response should include delivery statistics

  Scenario: Ask about low stock items
    Given product "Antibody A" with quantity 2 and reorder level 10
    And product "Reagent B" with quantity 50 and reorder level 20
    When I ask "What items are running low?"
    Then I should receive a response listing "Antibody A"
    And the response should not include "Reagent B"

  # 复杂查询
  Scenario: Ask for spending breakdown by category
    Given orders exist across multiple categories
    When I ask "Break down our spending by product category"
    Then I should receive a categorized breakdown
    And each category should have a total amount

  Scenario: Ask for order history summary
    Given 50 orders placed in the last 30 days
    When I ask "Summarize our order history for the past month"
    Then I should receive a summary with order count
    And the summary should include total value

  # 错误处理
  Scenario: Ask ambiguous question
    When I ask "Tell me about the lab"
    Then I should receive a helpful response asking for clarification
    And the response should suggest specific topics

  Scenario: Ask about non-existent data
    Given no orders exist
    When I ask "What is our most ordered product?"
    Then I should receive a response indicating no data available

  # 上下文感知
  Scenario: Ask follow-up question
    Given I previously asked about "Thermo Fisher"
    When I ask "Show me their recent orders"
    Then the response should relate to "Thermo Fisher"
    And the context should be maintained

  # 权限
  Scenario: Unauthenticated user cannot use ask
    Given I am not authenticated
    When I ask "What is our inventory?"
    Then I should receive a 401 error
