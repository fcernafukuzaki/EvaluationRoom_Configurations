import json
import logging
import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)

class ObjectWrapper:
    def __init__(self, s3_object):
        self.object = s3_object
        self.key = self.object.key

    def put(self, data):
        """
        Upload data to the object.

        :param data: The data to upload. This can either be bytes or a string. When this
                     argument is a string, it is interpreted as a file name, which is
                     opened in read bytes mode.
        """
        put_data = data
        if isinstance(data, str):
            try:
                put_data = open(data, 'rb')
            except IOError:
                logger.exception("Expected file name or binary data, got '%s'.", data)
                raise

        try:
            self.object.put(Body=put_data, ACL='public-read')
            self.object.wait_until_exists()
            logger.info(
                "Put object '%s' to bucket '%s'.", self.object.key,
                self.object.bucket_name)
        except ClientError:
            logger.exception(
                "Couldn't put object '%s' to bucket '%s'.", self.object.key,
                self.object.bucket_name)
            raise
        finally:
            if getattr(put_data, 'close', None):
                put_data.close()

    def get(self):
        """
        Gets the object.

        :return: The object data in bytes.
        """
        try:
            body = self.object.get()['Body'].read()
            logger.info(
                "Got object '%s' from bucket '%s'.",
                self.object.key, self.object.bucket_name)
        except ClientError:
            logger.exception(
                "Couldn't get object '%s' from bucket '%s'.",
                self.object.key, self.object.bucket_name)
            raise
        else:
            return body

    @staticmethod
    def list(bucket, prefix=None):
        """
        Lists the objects in a bucket, optionally filtered by a prefix.

        :param bucket: The bucket to query.
        :param prefix: When specified, only objects that start with this prefix are listed.
        :return: The list of objects.
        """
        try:
            if not prefix:
                objects = list(bucket.objects.all())
            else:
                objects = list(bucket.objects.filter(Prefix=prefix))
            logger.info("Got objects %s from bucket '%s'",
                        [o.key for o in objects], bucket.name)
        except ClientError:
            logger.exception("Couldn't get objects for bucket '%s'.", bucket.name)
            raise
        else:
            return objects

    def copy(self, dest_object):
        """
        Copies the object to another bucket.

        :param dest_object: The destination object initialized with a bucket and key.
        """
        try:
            dest_object.copy_from(CopySource={
                'Bucket': self.object.bucket_name,
                'Key': self.object.key
            })
            dest_object.wait_until_exists()
            logger.info(
                "Copied object from %s:%s to %s:%s.",
                self.object.key, self.object.bucket_name,
                dest_object.bucket_name, dest_object.key)
        except ClientError:
            logger.exception(
                "Couldn't copy object from %s/%s to %s/%s.",
                self.object.key, self.object.bucket_name,
                dest_object.bucket_name, dest_object.key)
            raise

    def put_acl(self, email):
        """
        Applies an ACL to the object that grants read access to an AWS user identified
        by email address.

        :param email: The email address of the user to grant access.
        """
        try:
            acl = self.object.Acl()
            # Putting an ACL overwrites the existing ACL, so append new grants
            # if you want to preserve existing grants.
            grants = acl.grants if acl.grants else []
            grants.append({
                'Grantee': {
                    'Type': 'AmazonCustomerByEmail',
                    'EmailAddress': email
                },
                'Permission': 'READ'
            })
            acl.put(
                AccessControlPolicy={
                    'Grants': grants,
                    'Owner': acl.owner
                }
            )
            logger.info("Granted read access to %s.", email)
        except ClientError:
            logger.exception("Couldn't add ACL to object '%s'.", self.object.key)
            raise

    def get_acl(self):
        """
        Gets the ACL of the object.

        :return: The ACL of the object.
        """
        try:
            acl = self.object.Acl()
            logger.info(
                "Got ACL for object %s owned by %s.",
                self.object.key, acl.owner['DisplayName'])
        except ClientError:
            logger.exception("Couldn't get ACL for object %s.", self.object.key)
            raise
        else:
            return acl

def upload_react_files():
    print('-'*88)
    print("Welcome to the Amazon S3 object demo!")
    print('-'*88)

    logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')

    s3_resource = boto3.resource('s3')
    bucket = s3_resource.Bucket(f'evaluationroom.com')
    try:
        bucket.create(
            CreateBucketConfiguration={
                'LocationConstraint': s3_resource.meta.client.meta.region_name})
    except ClientError as err:
        print(
            f"Couldn't create a bucket for the demo. Here's why: "
            f"{err.response['Error']['Message']}.")

    directory_file_names = '../../../EvaluationRoom_React/build/'
    list_file_names = ['js/index_exam.js',
                       'js/index_public.js',
                       'js/index.js']
    
    for file_name in list_file_names:
        object_key_file = f"{directory_file_names}{file_name}"
        object_key = file_name
        obj_wrapper = ObjectWrapper(bucket.Object(object_key))
        obj_wrapper.put(object_key_file)
        print(f"Put file object with key {object_key} in bucket {bucket.name}.")
    
        try:
            obj_wrapper.put_acl('fcernaf@gmail.com')
            acl = obj_wrapper.get_acl()
            print(f"Put ACL grants on object {obj_wrapper.key}: {json.dumps(acl.grants)}")
        except ClientError as error:
            if error.response['Error']['Code'] == 'UnresolvableGrantByEmailAddress':
                print('*'*88)
                print("This demo couldn't apply the ACL to the object because the email\n"
                    "address specified as the grantee is for a test user who does not\n"
                    "exist. For this request to succeed, you must replace the grantee\n"
                    "email with one for an existing AWS user.")
                print('*' * 88)
            else:
                raise

    print('-'*88)

if __name__ == '__main__':
    upload_react_files()