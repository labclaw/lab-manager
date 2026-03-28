# 文档处理流水线 — 扫描文档从上传到入库的完整路径
Feature: Document Intake Pipeline
  As a lab manager at the lab
  I want scanned documents to be processed through OCR and extraction
  So that order data enters our system accurately with human verification

  # 创建新文档记录
  Scenario: Create a new document record
    When I create a document "Scan_20260317_packing_list.jpg" at path "Scan_20260317_packing_list.jpg"
    Then the document should be created with status "pending"
    And the document should have file_name "Scan_20260317_packing_list.jpg"

  # 文档列表与过滤
  Scenario: List documents with status filter
    Given the following documents exist:
      | file_name       | status       | vendor_name          |
      | scan_001.jpg    | approved     | Fisher Scientific    |
      | scan_002.jpg    | needs_review | Sigma-Aldrich        |
      | scan_003.jpg    | rejected     | VWR International    |
      | scan_004.jpg    | needs_review | Thermo Fisher        |
    When I list documents with status "needs_review"
    Then I should see 2 documents
    And all documents should have status "needs_review"

  # 审核通过 → 自动创建订单
  Scenario: Approve document creates order
    Given a document with status "needs_review" and extracted data:
      | field          | value                  |
      | vendor_name    | Fisher Scientific      |
      | document_type  | packing_list           |
      | po_number      | PO-10865382            |
      | delivery_number| Y60066255001           |
    And the document has extracted items:
      | catalog_number | description            | quantity | unit |
      | 21-171-4       | Bores Oocyte Injector  | 3        | PK   |
    When I approve the document reviewed by "Robert"
    Then the document status should be "approved"
    And the document reviewed_by should be "Robert"
    And an order should be created with po_number "PO-10865382"
    And the order should have 1 item with catalog "21-171-4"

  # 拒绝文档
  Scenario: Reject document with reason
    Given a document with status "needs_review"
    When I reject the document with reason "Duplicate scan - same as doc #42"
    Then the document status should be "rejected"
    And the document review_notes should contain "Duplicate scan"

  # 文档统计
  Scenario: Document statistics
    Given 10 documents with status "approved"
    And 5 documents with status "needs_review"
    And 2 documents with status "rejected"
    When I request document statistics
    Then the total should be 17
    And approved count should be 10
    And needs_review count should be 5
