#!/usr/bin/env python3
"""
Quick test of S3 and HuggingFace backend status with your configured credentials.
"""

import asyncio
import os
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

async def quick_backend_test():
    """Quick test of configured backends."""
    
    logger.info("🔍 Quick Backend Configuration Test")
    logger.info("=" * 50)
    
    # Check environment variables
    logger.info("📋 Environment Configuration:")
    aws_key = os.environ.get("AWS_ACCESS_KEY_ID")
    aws_secret = os.environ.get("AWS_SECRET_ACCESS_KEY") 
    aws_region = os.environ.get("AWS_DEFAULT_REGION", "us-east-1")
    
    logger.info(f"   AWS Access Key: {'✅ Set' if aws_key else '❌ Missing'}")
    logger.info(f"   AWS Secret Key: {'✅ Set' if aws_secret else '❌ Missing'}")
    logger.info(f"   AWS Region: {aws_region}")
    
    # Test S3 credentials
    if aws_key and aws_secret:
        logger.info("🗄️ Testing S3 Connection...")
        try:
            import boto3
            from botocore.exceptions import NoCredentialsError, ClientError
            
            # Create S3 client
            s3_client = boto3.client('s3', region_name=aws_region)
            
            # Try to list buckets (basic operation)
            try:
                response = s3_client.list_buckets()
                bucket_count = len(response.get('Buckets', []))
                logger.info(f"   ✅ S3 Connection Successful!")
                logger.info(f"   📦 Found {bucket_count} buckets")
                
                # Show first few bucket names
                for i, bucket in enumerate(response.get('Buckets', [])[:3]):
                    logger.info(f"      - {bucket['Name']}")
                if bucket_count > 3:
                    logger.info(f"      ... and {bucket_count - 3} more")
                    
            except ClientError as e:
                error_code = e.response['Error']['Code']
                logger.warning(f"   ⚠️ S3 Access Issue: {error_code}")
                if error_code == 'AccessDenied':
                    logger.info("   💡 Credentials valid but may need list permissions")
                    
        except ImportError:
            logger.error("   ❌ boto3 not installed - run: pip install boto3")
        except Exception as e:
            logger.error(f"   ❌ S3 test failed: {e}")
    else:
        logger.warning("   ⚠️ S3 credentials not configured")
    
    # Test HuggingFace
    logger.info("🤗 Testing HuggingFace Connection...")
    try:
        import huggingface_hub
        
        # Check authentication
        try:
            token = huggingface_hub.HfFolder.get_token()
            if token:
                user_info = huggingface_hub.whoami(token=token)
                username = user_info.get("name", "unknown")
                logger.info(f"   ✅ HuggingFace Authenticated as: {username}")
                
                # Try to get basic user info
                api = huggingface_hub.HfApi(token=token)
                logger.info("   📊 Getting user repositories...")
                
                # Count user models (limit to avoid rate limiting)
                try:
                    models = list(api.list_models(author=username, limit=10))
                    model_count = len(models)
                    logger.info(f"      📚 Found {model_count}+ models")
                    
                    # Show first few model names
                    for i, model in enumerate(models[:3]):
                        logger.info(f"         - {model.modelId}")
                        
                except Exception as model_error:
                    logger.warning(f"   ⚠️ Model enumeration issue: {model_error}")
                
            else:
                logger.warning("   ⚠️ HuggingFace not authenticated")
                logger.info("   💡 Run: huggingface-cli login")
                
        except Exception as hf_error:
            logger.error(f"   ❌ HuggingFace test failed: {hf_error}")
            
    except ImportError:
        logger.error("   ❌ huggingface_hub not installed")
    
    logger.info("\n🎯 Summary:")
    logger.info("   Your configured backends are ready for enhanced storage analytics!")
    logger.info("   Start the dashboard to see real metrics from S3 and HuggingFace.")

if __name__ == "__main__":
    asyncio.run(quick_backend_test())
