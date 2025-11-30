import time
import json
import mysql.connector
from datetime import datetime

DB_CONFIG = {
    'host': '10.0.3.210',
    'user': 'root',
    'password': 'secret',
    'charset': 'utf8mb4'
}

class DatabaseConnector:
    def __init__(self):
        self.connections = {}
    
    def get_connection(self, database):
        if database not in self.connections:
            config = DB_CONFIG.copy()
            config['database'] = database
            self.connections[database] = mysql.connector.connect(**config)
        return self.connections[database]
    
    def close_connections(self):
        for conn in self.connections.values():
            if conn.is_connected():
                conn.close()

class ResourceParser:
    def parse_instance(self, instance_data, flavor_name=None):
        return {
            "id": instance_data['uuid'],
            "name": instance_data['display_name'],
            "type": "instance",
            "status": instance_data['vm_state'],
            "created_at": instance_data['created_at'].strftime("%Y-%m-%dT%H:%M:%SZ") if instance_data['created_at'] else None,
            "metadata": {
                "owner": instance_data['project_id'],
                "flavor": flavor_name,
            },
        }

    def parse_volume(self, volume_data):
        return {
            "id": volume_data['volume_id'],
            "name": f"volume-{volume_data['volume_id'][:8]}",
            "type": "volume",
            "status": "attached" if volume_data['instance_uuid'] else "available",
            "created_at": volume_data['created_at'].strftime("%Y-%m-%dT%H:%M:%SZ") if volume_data['created_at'] else None,
            "metadata": {
                "owner": volume_data.get('project_id', 'unknown'),
                "size_gb": volume_data['volume_size'],
            },
        }

    def parse_floating_ip(self, fip_data, created_at=None):
        return {
            "id": fip_data['id'],
            "name": fip_data['floating_ip_address'],
            "type": "floating_ip",
            "status": "associated" if fip_data['fixed_ip_address'] else "unassociated",
            "created_at": created_at.strftime("%Y-%m-%dT%H:%M:%SZ") if created_at else None,
            "metadata": {"tenant_id": fip_data['project_id']}
        }

class ResourceCollector:
    def __init__(self):
        self.db = DatabaseConnector()
        self.parser = ResourceParser()

    def collect_instances(self):
        try:
            nova_cell1 = self.db.get_connection('nova_cell1')
            nova_api = self.db.get_connection('nova_api')
            
            cursor = nova_cell1.cursor(dictionary=True)
            flavor_cursor = nova_api.cursor(dictionary=True)
            
            flavor_cursor.execute("SELECT id, name FROM flavors")
            flavors = {row['id']: row['name'] for row in flavor_cursor.fetchall()}
            flavor_cursor.close()
            
            cursor.execute("""
                SELECT uuid, display_name, vm_state, instance_type_id, 
                       created_at, project_id 
                FROM instances 
                WHERE deleted = 0 OR deleted IS NULL
            """)
            
            instances = []
            for row in cursor.fetchall():
                flavor_name = flavors.get(row['instance_type_id'], 'unknown')
                instances.append(self.parser.parse_instance(row, flavor_name))
            
            cursor.close()
            return instances
            
        except Exception as e:
            print(f"[WARN] Failed to collect instances: {e}")
            return []

    def collect_volumes(self):
        try:
            nova_cell1 = self.db.get_connection('nova_cell1')
            cursor = nova_cell1.cursor(dictionary=True)
            
            cursor.execute("""
                SELECT DISTINCT volume_id, volume_size, instance_uuid, 
                       created_at, deleted
                FROM block_device_mapping 
                WHERE volume_id IS NOT NULL 
                AND (deleted = 0 OR deleted IS NULL)
            """)
            
            volumes = []
            for row in cursor.fetchall():
                if row['volume_id']:
                    volumes.append(self.parser.parse_volume(row))
            
            cursor.close()
            return volumes
            
        except Exception as e:
            print(f"[WARN] Failed to collect volumes: {e}")
            return []

    def collect_floating_ips(self):
        try:
            neutron = self.db.get_connection('neutron')
            cursor = neutron.cursor(dictionary=True)
            
            cursor.execute("""
                SELECT f.id, f.floating_ip_address, f.fixed_ip_address, 
                       f.project_id, s.created_at
                FROM floatingips f
                LEFT JOIN standardattributes s ON f.standard_attr_id = s.id
            """)
            
            floating_ips = []
            for row in cursor.fetchall():
                floating_ips.append(self.parser.parse_floating_ip(row, row['created_at']))
            
            cursor.close()
            return floating_ips
            
        except Exception as e:
            print(f"[WARN] Failed to collect floating IPs: {e}")
            return []

class ResourcePuller:
    def __init__(self):
        self.collector = ResourceCollector()

    def pull_data(self):
        try:
            instances = self.collector.collect_instances()
            volumes = self.collector.collect_volumes()
            floating_ips = self.collector.collect_floating_ips()

            message = {
                "time": time.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "resources": instances + volumes + floating_ips,
            }
            print(json.dumps(message, indent=2))
            return message
        finally:
            self.collector.db.close_connections()
