# 遥测与监控 — 系统健康和性能指标
Feature: Telemetry and Monitoring
  As a lab administrator
  I want to monitor system health and performance metrics
  So that I can ensure the lab management system runs smoothly

  Background:
    Given I am authenticated as staff "admin1"

  # 系统健康检查
  Scenario: Get system health status
    When I request the telemetry health endpoint
    Then I should receive a healthy status
    And the response should include database status
    And the response should include meilisearch status

  Scenario: Health check when database is slow
    Given the database response time is 5 seconds
    When I request the telemetry health endpoint
    Then I should receive a degraded status
    And the response should indicate database latency

  # 性能指标
  Scenario: Get API response time metrics
    Given the system has processed 100 requests
    When I request the telemetry metrics endpoint
    Then I should receive response time statistics
    And the metrics should include p50, p95, and p99 latencies

  Scenario: Get error rate metrics
    Given the system has recorded 10 errors out of 100 requests
    When I request the telemetry metrics endpoint
    Then the error rate should be 10%
    And the metrics should include error breakdown by type

  # 资源使用
  Scenario: Get memory usage metrics
    When I request the telemetry resources endpoint
    Then I should receive current memory usage
    And the response should include memory percentage

  Scenario: Get database connection pool status
    When I request the telemetry database endpoint
    Then I should receive connection pool statistics
    And the response should include active connections count
    And the response should include idle connections count

  # 请求追踪
  Scenario: Track API request with trace ID
    When I make an API request
    Then the response should include a trace ID header
    And the trace ID should be unique

  Scenario: Correlate requests across services
    Given I made a document upload request with trace ID "abc123"
    When I query the telemetry logs for trace ID "abc123"
    Then I should see the full request lifecycle
    And each step should have timestamps

  # 告警阈值
  Scenario: Alert on high error rate
    Given error rate alert threshold is set to 5%
    And current error rate is 8%
    When I request the telemetry alerts endpoint
    Then I should see an alert for high error rate
    And the alert should have severity "warning"

  Scenario: Alert on slow response time
    Given p95 latency threshold is set to 500ms
    And current p95 latency is 800ms
    When I request the telemetry alerts endpoint
    Then I should see an alert for slow response time

  # 公开端点
  Scenario: Public health endpoint without auth
    Given I am not authenticated
    When I request the public health endpoint
    Then I should receive a 200 response
    And the response should include basic status

  # 数据保留
  Scenario: Telemetry data retention
    Given telemetry data older than 30 days exists
    When the telemetry cleanup job runs
    Then old telemetry data should be archived or deleted
    And recent data should be preserved
