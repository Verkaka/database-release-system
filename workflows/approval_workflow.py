#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Approval Workflow Engine - 多级审批流程引擎
支持组长审批、DBA 审批（高危 SQL）、运维执行
"""

import uuid
import json
from dataclasses import dataclass, field, asdict
from typing import List, Dict, Optional, Set
from datetime import datetime
from enum import Enum


class ApprovalStatus(Enum):
    """审批状态"""
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXECUTED = "executed"


class ApprovalRole(Enum):
    """审批角色"""
    SUBMITTER = "submitter"
    TEAM_LEAD = "team_lead"
    DBA = "dba"
    OPS = "ops"


@dataclass
class Approval:
    """审批记录"""
    approver: str
    role: str
    action: str  # approved / rejected
    comment: str = ""
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())


@dataclass
class ApprovalRequest:
    """审批请求"""
    request_id: str
    submitter: str
    submitter_name: str = ""
    changes: List[Dict] = field(default_factory=list)
    status: str = ApprovalStatus.PENDING.value
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    approvals: List[Approval] = field(default_factory=list)
    executed_at: Optional[str] = None
    executed_by: Optional[str] = None
    
    def to_dict(self) -> Dict:
        return asdict(self)


class ApprovalWorkflow:
    """审批流程引擎"""
    
    def __init__(self, config: Optional[Dict] = None):
        """
        初始化审批流程
        
        Args:
            config: 配置字典，包含审批链和人员映射
                {
                    "approval_chain": ["team_lead", "dba"],
                    "dba_required_for_risk": ["high"],
                    "approvers": {
                        "team_lead": ["user1", "user2"],
                        "dba": ["dba1", "dba2"],
                        "ops": ["ops1"]
                    }
                }
        """
        self.config = config or {}
        self.approval_chain = self.config.get('approval_chain', ['team_lead', 'dba'])
        self.dba_required_risks = self.config.get('dba_required_for_risk', ['high'])
        self.approvers = self.config.get('approvers', {})
        
        # 存储审批请求
        self.requests: Dict[str, ApprovalRequest] = {}
    
    def create_request(
        self, 
        submitter: str, 
        changes: List[Dict],
        submitter_name: str = ""
    ) -> ApprovalRequest:
        """
        创建审批请求
        
        Args:
            submitter: 提交人 ID
            submitter_name: 提交人姓名
            changes: 变更列表
        
        Returns:
            ApprovalRequest 对象
        """
        request = ApprovalRequest(
            request_id=self._generate_id(),
            submitter=submitter,
            submitter_name=submitter_name or submitter,
            changes=changes
        )
        
        self.requests[request.request_id] = request
        return request
    
    def requires_dba_approval(self, changes: List[Dict]) -> bool:
        """
        判断是否需要 DBA 审批
        
        Args:
            changes: 变更列表
        
        Returns:
            True 需要 DBA 审批
        """
        for change in changes:
            risk = change.get('risk', 'low')
            if risk in self.dba_required_risks:
                return True
        return False
    
    def get_required_approvals(self, request: ApprovalRequest) -> Set[str]:
        """
        获取必需的审批角色集合
        
        Args:
            request: 审批请求
        
        Returns:
            必需的审批角色集合
        """
        required = {'team_lead'}  # 组长审批始终需要
        
        if self.requires_dba_approval(request.changes):
            required.add('dba')
        
        return required
    
    def approve(
        self, 
        request_id: str, 
        approver: str, 
        role: str,
        comment: str = ""
    ) -> Dict:
        """
        审批通过
        
        Args:
            request_id: 请求 ID
            approver: 审批人 ID
            role: 审批人角色
            comment: 审批意见
        
        Returns:
            审批结果
        """
        if request_id not in self.requests:
            return {'success': False, 'error': '请求不存在'}
        
        request = self.requests[request_id]
        
        if request.status != ApprovalStatus.PENDING.value:
            return {'success': False, 'error': f'请求状态为 {request.status}，无法审批'}
        
        # 添加审批记录
        approval = Approval(
            approver=approver,
            role=role,
            action='approved',
            comment=comment
        )
        request.approvals.append(approval)
        
        # 检查是否完成所有审批
        if self._is_fully_approved(request):
            request.status = ApprovalStatus.APPROVED.value
            return {
                'success': True,
                'message': '审批通过，所有必需审批已完成',
                'request': request.to_dict()
            }
        
        return {
            'success': True,
            'message': '审批通过，等待其他审批',
            'pending_roles': list(self._get_pending_roles(request)),
            'request': request.to_dict()
        }
    
    def reject(
        self, 
        request_id: str, 
        approver: str, 
        role: str,
        comment: str = ""
    ) -> Dict:
        """
        审批拒绝
        
        Args:
            request_id: 请求 ID
            approver: 审批人 ID
            role: 审批人角色
            comment: 拒绝原因
        
        Returns:
            审批结果
        """
        if request_id not in self.requests:
            return {'success': False, 'error': '请求不存在'}
        
        request = self.requests[request_id]
        
        # 添加拒绝记录
        approval = Approval(
            approver=approver,
            role=role,
            action='rejected',
            comment=comment
        )
        request.approvals.append(approval)
        request.status = ApprovalStatus.REJECTED.value
        
        return {
            'success': True,
            'message': '请求已拒绝',
            'request': request.to_dict()
        }
    
    def execute(
        self, 
        request_id: str, 
        executor: str
    ) -> Dict:
        """
        执行变更（运维）
        
        Args:
            request_id: 请求 ID
            executor: 执行人 ID
        
        Returns:
            执行结果
        """
        if request_id not in self.requests:
            return {'success': False, 'error': '请求不存在'}
        
        request = self.requests[request_id]
        
        if request.status != ApprovalStatus.APPROVED.value:
            return {'success': False, 'error': '请求尚未获得全部审批'}
        
        request.status = ApprovalStatus.EXECUTED.value
        request.executed_at = datetime.now().isoformat()
        request.executed_by = executor
        
        return {
            'success': True,
            'message': '变更已执行',
            'request': request.to_dict()
        }
    
    def _is_fully_approved(self, request: ApprovalRequest) -> bool:
        """检查是否完成所有必需审批"""
        required_roles = self.get_required_approvals(request)
        approved_roles = {
            a.role for a in request.approvals if a.action == 'approved'
        }
        return required_roles.issubset(approved_roles)
    
    def _get_pending_roles(self, request: ApprovalRequest) -> Set[str]:
        """获取待审批的角色集合"""
        required_roles = self.get_required_approvals(request)
        approved_roles = {
            a.role for a in request.approvals if a.action == 'approved'
        }
        return required_roles - approved_roles
    
    def _generate_id(self) -> str:
        """生成请求 ID"""
        return f"DB-{uuid.uuid4().hex[:8].upper()}"
    
    def get_request(self, request_id: str) -> Optional[ApprovalRequest]:
        """获取审批请求"""
        return self.requests.get(request_id)
    
    def list_requests(self, status: Optional[str] = None) -> List[ApprovalRequest]:
        """
        列出审批请求
        
        Args:
            status: 状态过滤（可选）
        
        Returns:
            请求列表
        """
        if status:
            return [
                r for r in self.requests.values() 
                if r.status == status
            ]
        return list(self.requests.values())
    
    def export_to_json(self, output_file: str):
        """导出所有请求到 JSON 文件"""
        data = {
            'exported_at': datetime.now().isoformat(),
            'total_requests': len(self.requests),
            'requests': [r.to_dict() for r in self.requests.values()]
        }
        
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)


if __name__ == "__main__":
    # 测试示例
    workflow = ApprovalWorkflow({
        'approval_chain': ['team_lead', 'dba'],
        'dba_required_for_risk': ['high', 'medium'],
        'approvers': {
            'team_lead': ['lead1', 'lead2'],
            'dba': ['dba1'],
            'ops': ['ops1']
        }
    })
    
    # 创建测试请求
    changes = [
        {'type': 'CREATE', 'target': 'TABLE users', 'risk': 'low'},
        {'type': 'ALTER', 'target': 'TABLE orders', 'risk': 'high'}
    ]
    
    request = workflow.create_request(
        submitter='dev1',
        submitter_name='张三',
        changes=changes
    )
    
    print(f"创建请求：{request.request_id}")
    print(f"需要审批角色：{workflow.get_required_approvals(request)}")
    
    # 模拟审批流程
    result = workflow.approve(request.request_id, 'lead1', 'team_lead', '同意')
    print(f"组长审批后：{result['message']}")
    
    result = workflow.approve(request.request_id, 'dba1', 'dba', '高危 SQL 已审核')
    print(f"DBA 审批后：{result['message']}")
    
    # 执行变更
    result = workflow.execute(request.request_id, 'ops1')
    print(f"执行结果：{result['message']}")
