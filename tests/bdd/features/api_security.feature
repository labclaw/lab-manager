# API 安全 — 输入验证和安全检查
Feature: API Security and Input Validation
  As a secure API
  I want to validate all inputs and prevent attacks
  So that the system remains protected

  Background:
    Given I am authenticated as staff "user1"

  # SQL 注入防护
  Scenario: SQL injection in product name
    When I create a product with name "'; DROP TABLE products; --"
    Then the product should be created with the literal name
    And no SQL injection should occur

  Scenario: SQL injection in search query
    When I search for "1' OR '1'='1"
    Then the search should be sanitized
    And no data leak should occur

  # XSS 防护
  Scenario: XSS in vendor name
    When I create a vendor with name "<script>alert('xss')</script>"
    Then the vendor name should be HTML-escaped in responses
    And the script should not execute

  Scenario: XSS in product description
    Given product with description containing "<img src=x onerror=alert(1)>"
    When I request the product details
    Then the HTML should be escaped or stripped
    And the response should be safe

  # 路径遍历
  Scenario: Path traversal in document upload
    When I upload a document with path "../../../etc/passwd"
    Then the request should be rejected
    And no file system access should occur

  # 请求大小限制
  Scenario: Upload exceeds size limit
    When I upload a file larger than 50MB
    Then I should receive a 413 Payload Too Large error
    And the error should indicate size limit

  Scenario: Request body too large
    When I send a request with 10MB JSON body
    Then I should receive a 413 error
    And memory should not be exhausted

  # 参数验证
  Scenario: Invalid UUID in path
    When I request product with ID "not-a-uuid"
    Then I should receive a 422 validation error
    And the error should specify UUID format

  Scenario: Negative quantity
    When I create an order with quantity -5
    Then I should receive a validation error
    And the error should indicate minimum value

  Scenario: Quantity exceeds maximum
    When I create an order with quantity 999999999
    Then I should receive a validation error
    And the error should indicate maximum value

  # 速率限制
  Scenario: Rate limit exceeded
    Given I have made 100 requests in the last minute
    When I make another request
    Then I should receive a 429 Too Many Requests error
    And the response should include retry-after header

  # CORS
  Scenario: CORS headers on preflight
    When I send an OPTIONS request
    Then appropriate CORS headers should be returned
    And allowed methods should be listed

  # 认证头
  Scenario: Invalid authorization header format
    When I send a request with malformed auth header
    Then I should receive a 401 error
    And the error should indicate auth format

  Scenario: Expired token
    Given my session token has expired
    When I make an authenticated request
    Then I should receive a 401 error
    And the error should indicate token expired

  # 批量操作限制
  Scenario: Bulk create exceeds limit
    When I try to create 1000 products in one request
    Then I should receive a validation error
    And the error should indicate batch size limit

  # 内容类型验证
  Scenario: Invalid content type
    When I send XML to a JSON endpoint
    Then I should receive a 415 Unsupported Media Type error
