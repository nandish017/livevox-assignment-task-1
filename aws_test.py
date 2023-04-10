import unittest
import os
import sys
from datetime import datetime, timezone , timedelta
import boto3

aws_access_key_id=os.environ['aws_access_key_id']
aws_secret_access_key=os.environ['aws_secret_access_key']
now = datetime.now(timezone.utc)


def get_asg_describe(asgname):
    asg_client = boto3.client('autoscaling',aws_access_key_id=aws_access_key_id,aws_secret_access_key=aws_secret_access_key,region_name='ap-south-1')
    asg_response = asg_client.describe_auto_scaling_groups(AutoScalingGroupNames=[asgname])
    return asg_response


def get_ec2_resp():
    ec2_client = boto3.client('ec2',aws_access_key_id=aws_access_key_id,aws_secret_access_key=aws_secret_access_key,region_name='ap-south-1')
    ins = ec2_client.describe_instances()['Reservations']
    return ins


def check_list_equal(lst):
    return len(set(lst)) == 1


class TestCaseA(unittest.TestCase):

    def setUp(self):
        self.asgname = "lv-test-cpu"
        self.ec2_client = boto3.client('ec2',aws_access_key_id=aws_access_key_id,aws_secret_access_key=aws_secret_access_key,region_name='ap-south-1')
        self.asg_client = boto3.client('autoscaling',aws_access_key_id=aws_access_key_id,aws_secret_access_key=aws_secret_access_key,region_name='ap-south-1')
        if not sys.warnoptions:
            import warnings
            warnings.simplefilter("ignore")

    def test_validate_instance(self):
        response = get_asg_describe(self.asgname)
        print(response)
        cap = ""
        req_cnt = 0
        for instance in response['AutoScalingGroups'][0]['Instances']:
            if instance['LifecycleState'] == 'InService':
                req_cnt += 1
        for group in response['AutoScalingGroups']:
            cap = group['DesiredCapacity']
            print("Desired instances", cap)
        self.assertEqual(req_cnt,cap)

    def test_check_avail_zone(self):
        response = self.ec2_client.describe_availability_zones()
        availability_zones = [zone['ZoneName'] for zone in response['AvailabilityZones']]
        print("Availability Zones:", availability_zones)
        zones = []
        ins = get_ec2_resp()
        for i in range(len(ins)):
            inst = ins[i]['Instances']
            for i in inst:
                zones.append(i['Placement']['AvailabilityZone'])
        print("All instance zone ", zones)
        print("Checking if different availability zones are used")
        self.assertFalse(check_list_equal(zones))
        print("different availability zones are used")

    def test_check_params(self):
        ins = get_ec2_resp()
        sec_grp = []
        IMG_ID = []
        vpcID = []
        for i in range(len(ins)):
            inst = ins[i]['Instances']
            for i in inst:
                sg1 = [sg['GroupId'] for sg in i['SecurityGroups']]
                IMG_ID.append(i['ImageId'])
                ind = self.ec2_client.describe_vpcs()
                vpcID.append(ind['Vpcs'][0]['VpcId'])
                sec_grp.append(sg1)
        print("Security grp",sec_grp)
        print("Image ID",IMG_ID)
        print("VPCID:",vpcID)

        if len(sec_grp)!=0:
            self.assertTrue(all(x==sec_grp[0] for x in sec_grp))
        else:
            print("Security Group is null")
            self.assertFalse(True)
        self.assertTrue(check_list_equal(IMG_ID))
        self.assertTrue(check_list_equal(vpcID))

    def test_check_uptime(self):
        ut={}
        ins = get_ec2_resp()
        for i in range(len(ins)):
            inst = ins[i]['Instances']
            for i in inst:
                launch_time = i['LaunchTime'].replace(tzinfo=timezone.utc)
                uptime = now - launch_time
                print("Instance ",i['InstanceId']," has been up for",uptime)
                ut[i['InstanceId']] = uptime
        key_list = list(ut.keys())
        val_list = list(ut.values())
        pos = val_list.index(max(ut.values()))
        print("Longest instance is running for ", max(ut.values()), "with instance id", key_list[pos])

    def test_check_scheduled_actions(self):
        import datetime
        crnt_time = datetime.datetime.now(datetime.timezone.utc)
        sa = self.asg_client.describe_scheduled_actions()['ScheduledUpdateGroupActions']

        nxt = None
        for act in sa:
            if crnt_time >= act['StartTime']:
                continue
            if nxt is None or act['StartTime'] < nxt['StartTime']:
                nxt = act

        if nxt is not None:
            time_until_nxt = nxt['StartTime'] - crnt_time
            elapsed_time = str(time_until_nxt).split('.')[0]
            print('The next scheduled action is ',nxt['ScheduledActionName'],' and will run in ', elapsed_time)
        else:
            print("There are no scheduled actions that have not yet started.")

    def test_check_tot_inst(self):

        now = datetime.now()
        start_of_day = datetime(now.year, now.month, now.day)
        print("Start of the day: ",start_of_day)
        response = self.asg_client.describe_scaling_activities()
        today_activities = [a for a in response['Activities'] if a['StartTime'].replace(tzinfo=None) >= start_of_day]

        launch_count = 0
        terminate_count = 0

        for activity in today_activities:
            if activity['StatusCode'] == 'Successful' and activity['Description'].startswith('Launching a new EC2 instance'):
                launch_count += 1
            elif activity['StatusCode'] == 'Successful' and activity['Description'].startswith('Terminating EC2 instance'):
                terminate_count += 1

        print("Total instances launched today:", launch_count)
        print("Total instances terminated today:", terminate_count)


if __name__ == '__main__':
    unittest.main()
