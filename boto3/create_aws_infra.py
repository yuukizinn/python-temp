import json
import boto3
import requests

class CreateAwsinfra():

	def __init__(self, access_key, secret_access_key):
		self.access_key = access_key
		self.secret_access_key = secret_access_key
		self.region_name = 'ap-northeast-1'
		self.availability_zone_1 = 'ap-northeast-1a'
		self.availability_zone_2 = 'ap-northeast-1c'

	# configメソッド
	def __awsConfig(self, service):
		# 引数で使用するサービスを指定、リージョン・アベイラビリティゾーンはインスタンス変数を指定
		client = boto3.client(
			service,
			aws_access_key_id = self.access_key,
			aws_secret_access_key = self.secret_access_key,
			region_name = self.region_name,
		)
		return client

	# タグ作成メソッド
	def __createTags(self, client, resource_id, tag_name):
		# 指定したidの各サービスにNameタグ、Ownerタグをつける
		tags = client.create_tags(
			Resources = [resource_id],
			Tags = [
				{'Key': 'Name', 'Value': tag_name},
				{'Key': 'Owner', 'Value': ""}
			]
		)

	# VPC作成メソッド
	def __createVpc(self):
		client = self.__awsConfig('ec2')
		# vpcの作成
		vpc = client.create_vpc(CidrBlock='10.0.0.0/16', InstanceTenancy='default')
		# vpcのidを取得
		resource_id = vpc['Vpc']['VpcId']
		# 作成したVPCにタグをつける
		tags = self.__createTags(client, resource_id, 'test-vpc')
		return resource_id

	# サブネット作成メソッド
	def __createSubnet(self, vpc_id, availability_zone, cidr_block, tag_name):
		client = self.__awsConfig('ec2')
		# サブネットの作成
		subnet = client.create_subnet(VpcId=vpc_id, AvailabilityZone=availability_zone, CidrBlock=cidr_block)
		# サブネットのidを取得
		resource_id = subnet['Subnet']['SubnetId']
		# 作成したサブネットにタグをつける
		tags = self.__createTags(client, resource_id, tag_name)
		return resource_id

	# パブリックサブネット作成メソッド
	def __createPublicSubnet(self, vpc_id):
		subnet_id = self.__createSubnet(vpc_id, self.availability_zone_1, '10.0.1.0/24', 'public_subnet_1a')
		return subnet_id

	# プライベートサブネット作成メソッド
	def __createPrivateSubnet(self, vpc_id):
		availability_zone_list = [self.availability_zone_1, self.availability_zone_2]
		cidr_block_list = ['10.0.2.0/24', '10.0.20.0/24']
		tag_name_list = ['private_subnet_1a', 'private_subnet_1c']
		subnet_id_list = []
		# アベイラビリティゾーン、CIDRブロックのリストをループさせ、作成したVPCにサブネットを作成
		for availability_zone, cidr_block, tag_name in zip(availability_zone_list, cidr_block_list, tag_name_list):
			subnet_id = self.__createSubnet(vpc_id, availability_zone, cidr_block, tag_name)
			subnet_id_list.append(subnet_id)
		return subnet_id_list

	# インターネットゲートウェイ作成、アタッチメソッド
	def __createInternetGateway(self, vpc_id):
		client = self.__awsConfig('ec2')
		# インターネットゲートウェイの作成
		internet_gateway = client.create_internet_gateway()
		# インターネットゲートウェイのidを取得
		internet_gateway_id = internet_gateway['InternetGateway']['InternetGatewayId']
		# 作成したインターネットゲートウェイにタグをつける
		tags = self.__createTags(client, internet_gateway_id, 'test-igw')
		# インターネットゲートウェイをアタッチ
		attach = client.attach_internet_gateway(VpcId=vpc_id, InternetGatewayId=internet_gateway_id)
		return internet_gateway_id

	# ルートテーブル作成メソッド
	def __createRouteTable(self, vpc_id):
		client = self.__awsConfig('ec2')
		# ルートテーブルの作成
		route_table = client.create_route_table(VpcId=vpc_id)
		# ルートテーブルのidを取得
		resource_id = route_table['RouteTable']['RouteTableId']
		# 作成したルートテーブルにタグをつける
		tags = self.__createTags(client, resource_id, 'test-public-route-table')
		return resource_id

	# カスタムルート作成メソッド
	def __createRoute(self, gateway_id, route_table_id, subnet_id):
		client = self.__awsConfig('ec2')
		# 作成したルートテーブルにカスタムルートを設定（送信先「0.0.0.0/0」）
		create_route = client.create_route(DestinationCidrBlock='0.0.0.0/0', GatewayId=gateway_id, RouteTableId=route_table_id)
		# サブネットに関連付け
		associate_route_subnet = client.associate_route_table(RouteTableId=route_table_id, SubnetId=subnet_id)
		# パブリックIPアドレスを自動的に受信するように設定
		attribute_subnet = client.modify_subnet_attribute(
			MapPublicIpOnLaunch={'Value': True},
			SubnetId = subnet_id
		)
		return create_route

	# セキュリティグループ作成メソッド
	def __createSecurityGroup(self, vpc_id, tag_name):
		client = self.__awsConfig('ec2')
		# セキュリティグループ作成
		security_group = client.create_security_group(VpcId=vpc_id, GroupName=tag_name, Description=tag_name)
		# 作成したセキュリティグループのidを取得
		security_group_id = security_group['GroupId']
		# 作成したセキュリティグループにタグをつける
		tags = self.__createTags(client, security_group_id, tag_name)
		return security_group_id

	# SSH用のキーペア作成メソッド
	def __createKeyPair(self, key_name):
		client = self.__awsConfig('ec2')
		# キーペアの作成
		key = client.create_key_pair(KeyName=key_name)
		# キーペアidの取得
		key_pair_id = key['KeyPairId']
		# 作成したキーペアを取得し、pemファイルを作成
		key_material = key['KeyMaterial']
		with open(key_name, mode='w') as f:
			f.write(key_material)
		# 作成したキーペアにタグをつける
		tags = self.__createTags(client, key_pair_id, 'test-key-pair')
		return key_name

	# EC2インスタンス作成メソッド
	def __createInstance(self, subnet_id, security_group_id, key_name):
		client = self.__awsConfig('ec2')
		#パブリックIPアドレスの自動割り当ての有効
		valid_auto_public_ip = client.modify_subnet_attribute(
			MapPublicIpOnLaunch={'Value': True},
			SubnetId = subnet_id
		)
		# EC2インスタンス作成
		ec2_instance = client.run_instances(
			ImageId='ami-04204a8960917fd92',
			MinCount=1,
			MaxCount=1,
			InstanceType='t2.micro',
			SecurityGroupIds=[security_group_id],
			KeyName=key_name,
			SubnetId=subnet_id
		)
		# インスタンスidの取得
		instance_id = ec2_instance['Instances'][0]['InstanceId']
		# インバウンドルール設定メソッド呼び出し
		inbound_rule = self.__settingInboundRules(security_group_id, 22)
		# 作成したインスタンスにタグをつける
		tags = self.__createTags(client, instance_id, 'test-web-server')
		return instance_id, security_group_id



	# インバウンドルール設定メソッド
	def __settingInboundRules(self, security_group_id, port):
		# clientのサービスをEC2に指定
		client = self.__awsConfig('ec2')

		# マイIP(現在のグローバルIPアドレス)を取得
		url = 'https://ifconfig.me'
		request = requests.get(url)
		ip_address = '{}/32'.format(request.text)

		# インバウンドルールの作成
		inbound_rule = client.authorize_security_group_ingress(
			GroupId=security_group_id,
			IpPermissions=[
				{
					'FromPort': port,
					'IpProtocol': 'tcp',
					'IpRanges': [
						{
							'CidrIp': ip_address,
							'Description': 'test inbound rule',
						},
					],
					'ToPort': port
				}
			]
		)

		# セキュリティグループルール（インバウンドルール）idの取得
		inbound_rule_id = inbound_rule['SecurityGroupRules'][0]['SecurityGroupRuleId']

		# 作成したインバウンドルールにタグをつける
		tags = self.__createTags(client, inbound_rule_id, 'test-inbound-rule-ssh')
		return inbound_rule



	def createInfra(self):
		with open("test.txt", 'a') as f:
			# vpc_id = self.__createVpc()
			# print("VPCを作成しました。")
			# f.write(f"vpc_id:{vpc_id}")

			# private_subnet_id_list = self.__createPrivateSubnet(vpc_id)
			# print("プライベートサブネットを作成しました。")
			# f.write(f"private_subnet_id_list:{private_subnet_id_list}\n")

			# public_subnet_id = self.__createPublicSubnet(vpc_id)
			# print("パブリックサブネットを作成しました。")
			# f.write(f"public_subnet_id:{public_subnet_id}\n")

			# internet_gateway_id = self.__createInternetGateway(vpc_id)
			# print("インターネットゲートウェイを作成しました。")
			# f.write(f"internet_gateway_id:{internet_gateway_id}\n")

			# route_table_id = self.__createRouteTable(vpc_id)
			# print("ルートテーブルを作成しました。")
			# f.write(f"route_table_id:{route_table_id}\n")

			# create_route = self.__createRoute(internet_gateway_id, route_table_id, public_subnet_id)
			# print("カスタムルートを作成、ルートテーブルにアタッチしました。")
			# f.write(f"create_route:{create_route}\n")

			# security_group_id = self.__createSecurityGroup(vpc_id, 'test-security-group')
			# print("セキュリティグループを作成しました。")
			# f.write(f"security_group_id:{security_group_id}\n")

			# key_name = 'test-key.pem'
			# _ = self.__createKeyPair(key_name)
			# print("キーペアを作成しました。")
			# f.write(f"key_name:{key_name}\n")

			# instance_id, security_group_id = self.__createInstance(public_subnet_id, security_group_id, key_name)
			instance_id, security_group_id = self.__createInstance("subnet-09ce9f5bb9e1c1d21", "sg-07519acb396e07293", 'test-key.pem')
			print("インスタンスを作成しました。")
			f.write(f"instance_id:{instance_id}")
			f.write(f"security_group_id:{security_group_id}")



access_key = ""
secret_access_key = ""

# client = boto3.client(
# 	'ec2',
# 	aws_access_key_id=access_key,
# 	aws_secret_access_key=secret_access_key,
# 	region_name="ap-northeast-1"
# )
# print(client.describe_vpcs())

aws = CreateAwsinfra(access_key, secret_access_key)
create_infra = aws.createInfra()


# with open("test.json", 'w') as f:
	# json.dump(client.describe_vpcs(), f, indent=4)
