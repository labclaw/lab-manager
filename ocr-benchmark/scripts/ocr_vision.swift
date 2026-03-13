import AppKit
import Foundation
import Vision

struct OCRLine: Codable {
    let text: String
    let confidence: Double
    let bbox: [Double]
}

struct OCRDocument: Codable {
    let file: String
    let fullText: String
    let lines: [OCRLine]
}

struct OCRFailure: Codable {
    let file: String
    let error: String
}

struct OCRRun: Codable {
    let documents: [OCRDocument]
    let failures: [OCRFailure]
}

func loadImage(at path: String) -> NSImage? {
    NSImage(contentsOfFile: path)
}

func cgImage(from image: NSImage) -> CGImage? {
    var rect = CGRect(origin: .zero, size: image.size)
    return image.cgImage(forProposedRect: &rect, context: nil, hints: nil)
}

func recognizeText(in fileURL: URL) throws -> OCRDocument {
    guard let image = loadImage(at: fileURL.path),
          let cgImage = cgImage(from: image) else {
        throw NSError(domain: "ocr_vision", code: 1, userInfo: [NSLocalizedDescriptionKey: "Unable to load image \(fileURL.path)"])
    }

    let request = VNRecognizeTextRequest()
    request.recognitionLevel = .accurate
    request.usesLanguageCorrection = true
    request.minimumTextHeight = 0.005

    let handler = VNImageRequestHandler(cgImage: cgImage, options: [:])
    try handler.perform([request])

    let observations = request.results ?? []
    let lines = observations.compactMap { observation -> OCRLine? in
        guard let candidate = observation.topCandidates(1).first else {
            return nil
        }
        let box = observation.boundingBox
        return OCRLine(
            text: candidate.string,
            confidence: Double(candidate.confidence),
            bbox: [Double(box.origin.x), Double(box.origin.y), Double(box.size.width), Double(box.size.height)]
        )
    }

    let fullText = lines.map(\.text).joined(separator: "\n")
    return OCRDocument(file: fileURL.lastPathComponent, fullText: fullText, lines: lines)
}

let args = CommandLine.arguments
guard args.count == 3 else {
    fputs("usage: swift ocr_vision.swift <input_dir> <output_json>\n", stderr)
    exit(1)
}

let inputDir = URL(fileURLWithPath: args[1], isDirectory: true)
let outputURL = URL(fileURLWithPath: args[2])
let fm = FileManager.default

let files = try fm.contentsOfDirectory(at: inputDir, includingPropertiesForKeys: nil)
    .filter { ["png", "jpg", "jpeg", "tif", "tiff"].contains($0.pathExtension.lowercased()) }
    .sorted { $0.lastPathComponent < $1.lastPathComponent }

var docs: [OCRDocument] = []
var failures: [OCRFailure] = []
for file in files {
    do {
        let doc = try recognizeText(in: file)
        docs.append(doc)
        fputs("processed \(file.lastPathComponent)\n", stderr)
    } catch {
        failures.append(OCRFailure(file: file.lastPathComponent, error: error.localizedDescription))
        fputs("failed \(file.lastPathComponent): \(error.localizedDescription)\n", stderr)
    }
}
let encoder = JSONEncoder()
encoder.outputFormatting = [.prettyPrinted, .sortedKeys]
let run = OCRRun(documents: docs, failures: failures)
try encoder.encode(run).write(to: outputURL)
print("wrote \(docs.count) docs and \(failures.count) failures to \(outputURL.path)")
