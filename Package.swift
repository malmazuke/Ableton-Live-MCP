// swift-tools-version: 6.0

import PackageDescription

let package = Package(
    name: "AbletonMCP",
    platforms: [
        .macOS(.v14)
    ],
    dependencies: [
        .package(url: "https://github.com/modelcontextprotocol/swift-sdk.git", from: "0.11.0"),
    ],
    targets: [
        .executableTarget(
            name: "AbletonMCP",
            dependencies: [
                .product(name: "MCP", package: "swift-sdk"),
            ],
            path: "Sources/AbletonMCP"
        ),
        .testTarget(
            name: "AbletonMCPTests",
            dependencies: ["AbletonMCP"],
            path: "Tests/AbletonMCPTests"
        ),
    ]
)
