# 前端路由 — 哈希路由、导航、深度链接
Feature: Frontend Hash Routing
  As a lab scientist at Shen Lab
  I want the app to have bookmarkable URLs and working back/forward buttons
  So that I can share links to specific views and navigate naturally

  Background:
    Given I am logged in as a scientist

  # 默认路由
  Scenario: Default route loads dashboard
    When I open the app without a hash
    Then the URL hash should be "#/dashboard"
    And the dashboard view should be visible

  # 导航栏路由
  Scenario Outline: Navbar buttons navigate to correct views
    When I click the "<button>" nav button
    Then the URL hash should be "#/<route>"
    And the "<view>" view should be visible

    Examples:
      | button    | route     | view      |
      | Dashboard | dashboard | dashboard |
      | Documents | documents | documents |
      | Review    | review    | review    |
      | Inventory | inventory | inventory |
      | Orders    | orders    | orders    |

  # 直接访问哈希路由
  Scenario: Direct hash URL loads correct view
    When I navigate to "#/inventory"
    Then the inventory view should be visible
    And the Inventory nav button should be active

  # 未知路由重定向
  Scenario: Unknown route redirects to dashboard
    When I navigate to "#/nonexistent"
    Then the URL hash should be "#/dashboard"
    And the dashboard view should be visible

  # 浏览器后退按钮
  Scenario: Browser back button works
    When I navigate to "#/documents"
    And I navigate to "#/inventory"
    And I press the browser back button
    Then the documents view should be visible

  # 搜索路由带参数
  Scenario: Search route with query parameter
    When I navigate to "#/search?q=antibody"
    Then the search view should be visible
    And the search input should contain "antibody"
    And search results should be loading or displayed
