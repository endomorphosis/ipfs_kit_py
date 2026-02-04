#!/usr/bin/env python3
"""
Mobile SDK for IPFS Kit (iOS/Android)

Provides mobile-friendly bindings and optimizations for iOS and Android platforms.
This module generates SDK packages for mobile platforms.
"""

import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class MobileSDKGenerator:
    """
    Generate mobile SDK packages for iOS and Android.
    
    Creates platform-specific bindings and builds optimized libraries
    for mobile deployment.
    """
    
    def __init__(self, output_dir: Optional[str] = None):
        """Initialize mobile SDK generator."""
        self.output_dir = output_dir or os.path.expanduser("~/.ipfs_kit/mobile_sdk")
        os.makedirs(self.output_dir, exist_ok=True)
        
        logger.info(f"Mobile SDK generator initialized at {self.output_dir}")
    
    def generate_ios_sdk(self) -> Dict[str, Any]:
        """
        Generate iOS SDK package.
        
        Creates Swift bindings and builds XCFramework for iOS/iPadOS.
        
        Returns:
            Dictionary with SDK generation results
        """
        try:
            ios_dir = os.path.join(self.output_dir, "ios")
            os.makedirs(ios_dir, exist_ok=True)
            
            # Generate Swift bridge
            swift_bridge = self._generate_swift_bridge()
            bridge_path = os.path.join(ios_dir, "IPFSKitBridge.swift")
            with open(bridge_path, 'w') as f:
                f.write(swift_bridge)
            
            # Generate Package.swift
            package_swift = self._generate_swift_package()
            package_path = os.path.join(ios_dir, "Package.swift")
            with open(package_path, 'w') as f:
                f.write(package_swift)
            
            # Generate Podspec
            podspec = self._generate_podspec()
            podspec_path = os.path.join(ios_dir, "IPFSKit.podspec")
            with open(podspec_path, 'w') as f:
                f.write(podspec)
            
            # Generate README
            readme = self._generate_ios_readme()
            readme_path = os.path.join(ios_dir, "README.md")
            with open(readme_path, 'w') as f:
                f.write(readme)
            
            logger.info(f"Generated iOS SDK at {ios_dir}")
            
            return {
                "success": True,
                "platform": "iOS",
                "output_dir": ios_dir,
                "files": [
                    "IPFSKitBridge.swift",
                    "Package.swift",
                    "IPFSKit.podspec",
                    "README.md"
                ]
            }
        except Exception as e:
            logger.error(f"Error generating iOS SDK: {e}")
            return {"success": False, "error": str(e)}
    
    def generate_android_sdk(self) -> Dict[str, Any]:
        """
        Generate Android SDK package.
        
        Creates Kotlin bindings and builds AAR library for Android.
        
        Returns:
            Dictionary with SDK generation results
        """
        try:
            android_dir = os.path.join(self.output_dir, "android")
            os.makedirs(android_dir, exist_ok=True)
            
            # Generate Kotlin bridge
            kotlin_bridge = self._generate_kotlin_bridge()
            bridge_path = os.path.join(android_dir, "IPFSKitBridge.kt")
            with open(bridge_path, 'w') as f:
                f.write(kotlin_bridge)
            
            # Generate build.gradle
            gradle = self._generate_gradle_build()
            gradle_path = os.path.join(android_dir, "build.gradle")
            with open(gradle_path, 'w') as f:
                f.write(gradle)
            
            # Generate AndroidManifest.xml
            manifest = self._generate_android_manifest()
            manifest_path = os.path.join(android_dir, "AndroidManifest.xml")
            with open(manifest_path, 'w') as f:
                f.write(manifest)
            
            # Generate README
            readme = self._generate_android_readme()
            readme_path = os.path.join(android_dir, "README.md")
            with open(readme_path, 'w') as f:
                f.write(readme)
            
            logger.info(f"Generated Android SDK at {android_dir}")
            
            return {
                "success": True,
                "platform": "Android",
                "output_dir": android_dir,
                "files": [
                    "IPFSKitBridge.kt",
                    "build.gradle",
                    "AndroidManifest.xml",
                    "README.md"
                ]
            }
        except Exception as e:
            logger.error(f"Error generating Android SDK: {e}")
            return {"success": False, "error": str(e)}
    
    def _generate_swift_bridge(self) -> str:
        """Generate Swift bridge code."""
        return """//
// IPFSKitBridge.swift
// IPFS Kit Mobile SDK for iOS
//

import Foundation

@objc public class IPFSKit: NSObject {
    private var apiEndpoint: String
    private var apiPort: Int
    
    @objc public init(endpoint: String = "http://localhost", port: Int = 5001) {
        self.apiEndpoint = endpoint
        self.apiPort = port
        super.init()
    }
    
    // MARK: - Core IPFS Operations
    
    @objc public func add(_ data: Data, completion: @escaping (String?, Error?) -> Void) {
        let url = URL(string: "\\(apiEndpoint):\\(apiPort)/api/v0/add")!
        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.httpBody = data
        
        let task = URLSession.shared.dataTask(with: request) { data, response, error in
            if let error = error {
                completion(nil, error)
                return
            }
            
            guard let data = data else {
                completion(nil, NSError(domain: "IPFSKit", code: -1, userInfo: [NSLocalizedDescriptionKey: "No data received"]))
                return
            }
            
            do {
                if let json = try JSONSerialization.jsonObject(with: data) as? [String: Any],
                   let cid = json["Hash"] as? String {
                    completion(cid, nil)
                } else {
                    completion(nil, NSError(domain: "IPFSKit", code: -1, userInfo: [NSLocalizedDescriptionKey: "Invalid response"]))
                }
            } catch {
                completion(nil, error)
            }
        }
        
        task.resume()
    }
    
    @objc public func get(_ cid: String, completion: @escaping (Data?, Error?) -> Void) {
        let url = URL(string: "\\(apiEndpoint):\\(apiPort)/api/v0/cat?arg=\\(cid)")!
        
        let task = URLSession.shared.dataTask(with: url) { data, response, error in
            if let error = error {
                completion(nil, error)
                return
            }
            
            completion(data, nil)
        }
        
        task.resume()
    }
    
    @objc public func pin(_ cid: String, completion: @escaping (Bool, Error?) -> Void) {
        let url = URL(string: "\\(apiEndpoint):\\(apiPort)/api/v0/pin/add?arg=\\(cid)")!
        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        
        let task = URLSession.shared.dataTask(with: request) { _, response, error in
            if let error = error {
                completion(false, error)
                return
            }
            
            if let httpResponse = response as? HTTPURLResponse {
                completion(httpResponse.statusCode == 200, nil)
            } else {
                completion(false, nil)
            }
        }
        
        task.resume()
    }
    
    @objc public func unpin(_ cid: String, completion: @escaping (Bool, Error?) -> Void) {
        let url = URL(string: "\\(apiEndpoint):\\(apiPort)/api/v0/pin/rm?arg=\\(cid)")!
        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        
        let task = URLSession.shared.dataTask(with: request) { _, response, error in
            if let error = error {
                completion(false, error)
                return
            }
            
            if let httpResponse = response as? HTTPURLResponse {
                completion(httpResponse.statusCode == 200, nil)
            } else {
                completion(false, nil)
            }
        }
        
        task.resume()
    }
    
    // MARK: - Async/Await Support (iOS 13+)
    
    @available(iOS 13.0, *)
    public func add(_ data: Data) async throws -> String {
        try await withCheckedThrowingContinuation { continuation in
            add(data) { cid, error in
                if let error = error {
                    continuation.resume(throwing: error)
                } else if let cid = cid {
                    continuation.resume(returning: cid)
                } else {
                    continuation.resume(throwing: NSError(domain: "IPFSKit", code: -1))
                }
            }
        }
    }
    
    @available(iOS 13.0, *)
    public func get(_ cid: String) async throws -> Data {
        try await withCheckedThrowingContinuation { continuation in
            get(cid) { data, error in
                if let error = error {
                    continuation.resume(throwing: error)
                } else if let data = data {
                    continuation.resume(returning: data)
                } else {
                    continuation.resume(throwing: NSError(domain: "IPFSKit", code: -1))
                }
            }
        }
    }
}
"""
    
    def _generate_swift_package(self) -> str:
        """Generate Package.swift for Swift Package Manager."""
        return """// swift-tools-version:5.5
import PackageDescription

let package = Package(
    name: "IPFSKit",
    platforms: [
        .iOS(.v13),
        .macOS(.v10_15)
    ],
    products: [
        .library(
            name: "IPFSKit",
            targets: ["IPFSKit"]),
    ],
    targets: [
        .target(
            name: "IPFSKit",
            dependencies: []),
        .testTarget(
            name: "IPFSKitTests",
            dependencies: ["IPFSKit"]),
    ]
)
"""
    
    def _generate_podspec(self) -> str:
        """Generate CocoaPods podspec."""
        return """Pod::Spec.new do |s|
  s.name             = 'IPFSKit'
  s.version          = '0.3.0'
  s.summary          = 'IPFS Kit Mobile SDK for iOS'
  s.description      = <<-DESC
    Mobile SDK for IPFS Kit providing high-level APIs for iOS applications.
    Enables decentralized storage in mobile apps.
  DESC
  s.homepage         = 'https://github.com/endomorphosis/ipfs_kit_py'
  s.license          = { :type => 'AGPL-3.0', :file => 'LICENSE' }
  s.author           = { 'Benjamin Barber' => 'starworks5@gmail.com' }
  s.source           = { :git => 'https://github.com/endomorphosis/ipfs_kit_py.git', :tag => s.version.to_s }
  
  s.ios.deployment_target = '13.0'
  s.swift_version = '5.0'
  
  s.source_files = 'IPFSKitBridge.swift'
end
"""
    
    def _generate_ios_readme(self) -> str:
        """Generate iOS README."""
        return """# IPFS Kit iOS SDK

Mobile SDK for IPFS Kit on iOS/iPadOS.

## Installation

### Swift Package Manager

Add to your `Package.swift`:

```swift
dependencies: [
    .package(url: "https://github.com/endomorphosis/ipfs_kit_py.git", from: "0.3.0")
]
```

### CocoaPods

Add to your `Podfile`:

```ruby
pod 'IPFSKit', '~> 0.3.0'
```

## Usage

```swift
import IPFSKit

// Initialize
let ipfs = IPFSKit(endpoint: "http://localhost", port: 5001)

// Add content (callback style)
let data = "Hello, IPFS!".data(using: .utf8)!
ipfs.add(data) { cid, error in
    if let cid = cid {
        print("Added with CID: \\(cid)")
    }
}

// Add content (async/await style - iOS 13+)
Task {
    do {
        let cid = try await ipfs.add(data)
        print("Added with CID: \\(cid)")
        
        // Retrieve content
        let retrieved = try await ipfs.get(cid)
        print("Retrieved: \\(String(data: retrieved, encoding: .utf8) ?? "")")
    } catch {
        print("Error: \\(error)")
    }
}
```

## Requirements

- iOS 13.0+ / iPadOS 13.0+
- Xcode 13.0+
- Swift 5.5+

## License

AGPL-3.0 - See LICENSE file for details.
"""
    
    def _generate_kotlin_bridge(self) -> str:
        """Generate Kotlin bridge code."""
        return """package org.ipfskit.mobile

import android.content.Context
import kotlinx.coroutines.*
import okhttp3.*
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.RequestBody.Companion.toRequestBody
import org.json.JSONObject
import java.io.IOException

/**
 * IPFS Kit Mobile SDK for Android
 * 
 * Provides high-level APIs for interacting with IPFS from Android applications.
 */
class IPFSKit(
    private val endpoint: String = "http://localhost",
    private val port: Int = 5001
) {
    private val client = OkHttpClient()
    private val baseUrl = "$endpoint:$port"
    
    /**
     * Add data to IPFS
     * 
     * @param data Data to add
     * @param callback Callback with CID or error
     */
    fun add(data: ByteArray, callback: (String?, Exception?) -> Unit) {
        val url = "$baseUrl/api/v0/add"
        val requestBody = data.toRequestBody("application/octet-stream".toMediaType())
        
        val request = Request.Builder()
            .url(url)
            .post(requestBody)
            .build()
        
        client.newCall(request).enqueue(object : Callback {
            override fun onFailure(call: Call, e: IOException) {
                callback(null, e)
            }
            
            override fun onResponse(call: Call, response: Response) {
                response.use {
                    if (!response.isSuccessful) {
                        callback(null, IOException("Unexpected code $response"))
                        return
                    }
                    
                    try {
                        val json = JSONObject(response.body!!.string())
                        val cid = json.getString("Hash")
                        callback(cid, null)
                    } catch (e: Exception) {
                        callback(null, e)
                    }
                }
            }
        })
    }
    
    /**
     * Get data from IPFS
     * 
     * @param cid Content identifier
     * @param callback Callback with data or error
     */
    fun get(cid: String, callback: (ByteArray?, Exception?) -> Unit) {
        val url = "$baseUrl/api/v0/cat?arg=$cid"
        
        val request = Request.Builder()
            .url(url)
            .build()
        
        client.newCall(request).enqueue(object : Callback {
            override fun onFailure(call: Call, e: IOException) {
                callback(null, e)
            }
            
            override fun onResponse(call: Call, response: Response) {
                response.use {
                    if (!response.isSuccessful) {
                        callback(null, IOException("Unexpected code $response"))
                        return
                    }
                    
                    callback(response.body?.bytes(), null)
                }
            }
        })
    }
    
    /**
     * Pin content to IPFS
     * 
     * @param cid Content identifier
     * @param callback Callback with success status
     */
    fun pin(cid: String, callback: (Boolean, Exception?) -> Unit) {
        val url = "$baseUrl/api/v0/pin/add?arg=$cid"
        
        val request = Request.Builder()
            .url(url)
            .post("".toRequestBody())
            .build()
        
        client.newCall(request).enqueue(object : Callback {
            override fun onFailure(call: Call, e: IOException) {
                callback(false, e)
            }
            
            override fun onResponse(call: Call, response: Response) {
                callback(response.isSuccessful, null)
            }
        })
    }
    
    /**
     * Unpin content from IPFS
     * 
     * @param cid Content identifier
     * @param callback Callback with success status
     */
    fun unpin(cid: String, callback: (Boolean, Exception?) -> Unit) {
        val url = "$baseUrl/api/v0/pin/rm?arg=$cid"
        
        val request = Request.Builder()
            .url(url)
            .post("".toRequestBody())
            .build()
        
        client.newCall(request).enqueue(object : Callback {
            override fun onFailure(call: Call, e: IOException) {
                callback(false, e)
            }
            
            override fun onResponse(call: Call, response: Response) {
                callback(response.isSuccessful, null)
            }
        })
    }
    
    // Coroutine-based suspend functions
    
    /**
     * Add data to IPFS (suspend function)
     */
    suspend fun addAsync(data: ByteArray): String = withContext(Dispatchers.IO) {
        suspendCancellableCoroutine { continuation ->
            add(data) { cid, error ->
                if (error != null) {
                    continuation.resumeWith(Result.failure(error))
                } else if (cid != null) {
                    continuation.resumeWith(Result.success(cid))
                } else {
                    continuation.resumeWith(Result.failure(Exception("Unknown error")))
                }
            }
        }
    }
    
    /**
     * Get data from IPFS (suspend function)
     */
    suspend fun getAsync(cid: String): ByteArray = withContext(Dispatchers.IO) {
        suspendCancellableCoroutine { continuation ->
            get(cid) { data, error ->
                if (error != null) {
                    continuation.resumeWith(Result.failure(error))
                } else if (data != null) {
                    continuation.resumeWith(Result.success(data))
                } else {
                    continuation.resumeWith(Result.failure(Exception("Unknown error")))
                }
            }
        }
    }
}
"""
    
    def _generate_gradle_build(self) -> str:
        """Generate Gradle build file."""
        return """plugins {
    id 'com.android.library'
    id 'kotlin-android'
}

android {
    compileSdk 33
    
    defaultConfig {
        minSdk 21
        targetSdk 33
        versionCode 1
        versionName "0.3.0"
        
        testInstrumentationRunner "androidx.test.runner.AndroidJUnitRunner"
    }
    
    buildTypes {
        release {
            minifyEnabled false
            proguardFiles getDefaultProguardFile('proguard-android-optimize.txt'), 'proguard-rules.pro'
        }
    }
    
    compileOptions {
        sourceCompatibility JavaVersion.VERSION_1_8
        targetCompatibility JavaVersion.VERSION_1_8
    }
    
    kotlinOptions {
        jvmTarget = '1.8'
    }
}

dependencies {
    implementation 'org.jetbrains.kotlin:kotlin-stdlib:1.8.0'
    implementation 'org.jetbrains.kotlinx:kotlinx-coroutines-android:1.6.4'
    implementation 'com.squareup.okhttp3:okhttp:4.10.0'
    implementation 'androidx.core:core-ktx:1.10.0'
    
    testImplementation 'junit:junit:4.13.2'
    androidTestImplementation 'androidx.test.ext:junit:1.1.5'
    androidTestImplementation 'androidx.test.espresso:espresso-core:3.5.1'
}
"""
    
    def _generate_android_manifest(self) -> str:
        """Generate Android manifest."""
        return """<?xml version="1.0" encoding="utf-8"?>
<manifest xmlns:android="http://schemas.android.com/apk/res/android"
    package="org.ipfskit.mobile">
    
    <uses-permission android:name="android.permission.INTERNET" />
    <uses-permission android:name="android.permission.ACCESS_NETWORK_STATE" />
    
</manifest>
"""
    
    def _generate_android_readme(self) -> str:
        """Generate Android README."""
        return """# IPFS Kit Android SDK

Mobile SDK for IPFS Kit on Android.

## Installation

### Gradle

Add to your `build.gradle`:

```gradle
dependencies {
    implementation 'org.ipfskit:mobile:0.3.0'
}
```

## Usage

```kotlin
import org.ipfskit.mobile.IPFSKit
import kotlinx.coroutines.launch

// Initialize
val ipfs = IPFSKit(endpoint = "http://localhost", port = 5001)

// Add content (callback style)
val data = "Hello, IPFS!".toByteArray()
ipfs.add(data) { cid, error ->
    if (cid != null) {
        println("Added with CID: $cid")
    }
}

// Add content (coroutine style)
lifecycleScope.launch {
    try {
        val cid = ipfs.addAsync(data)
        println("Added with CID: $cid")
        
        // Retrieve content
        val retrieved = ipfs.getAsync(cid)
        println("Retrieved: ${String(retrieved)}")
    } catch (e: Exception) {
        println("Error: $e")
    }
}
```

## Requirements

- Android API 21+ (Android 5.0)
- Kotlin 1.8+

## License

AGPL-3.0 - See LICENSE file for details.
"""


# Convenience function
def create_mobile_sdk_generator(output_dir: Optional[str] = None) -> MobileSDKGenerator:
    """Create mobile SDK generator instance."""
    return MobileSDKGenerator(output_dir=output_dir)
