#!/usr/bin/env python
# 786

# Aldy source: cn.py
#   This file is subject to the terms and conditions defined in
#   file 'LICENSE', which is part of this source code package.


from typing import Dict, List, Tuple

import collections
import copy
import os

from . import lpinterface
from . import sam
from . import gene

from .common import *
from .gene import GeneRegion, CNConfig, Gene
from .sam import Sample
from .coverage import Coverage


# This region requires special handling
PCE_REGION = GeneRegion(11, 'pce') 
# Maximum allowed CN 
MAX_CN = 20.0


"""
Describes a potential (possibly optimal) copy-number configuration.
Members:
   score (float):
      ILP model error score (0 for user-provided solutions)
   solution (dict of str: int):
      dict of CN configurations where a value denotes the copy-number
      of each CN config (e.g. {1: 2} means that we have two copies
      of *1 CN config)
   region_cn (dict of gene.GeneRegion: int):
      dictionary of region CNs in this solution
"""
class CNSolution(nt('CNSolution', 'score solution region_cn gene'.split())):
   def position_cn(self, pos: int) -> float:
      try:
         g, region = self.gene.region_at(pos)
         return self.region_cn[g][region]
      except KeyError:
         return 0

   def __repr__(self):
      regions = sorted(set(r for g in self.region_cn for r in self.region_cn[g]))
      return 'CNSol[{:.2f}; sol=({}); cn={}]'.format(
         self.score,
         ','.join('*{}x{}'.format(*kv) for kv in self.solution.items()),
         '|'.join(
            ''.join(str(self.region_cn[g][r]) if r in self.region_cn[g] else '_' for r in regions)
            for g in sorted(self.region_cn)))



def estimate_cn(gene: Gene, sam: Sample, solver: str, 
                user_solution=None) -> List[CNSolution]:
   """
   Estimate optimal copy number configuration given the gene and the sample.
   Params:
      gene (gene.Gene): gene instance
      sam (sam.Sample): sample instance
      solver (str): 
         ILP solver to use. Check lpinterface.py for available solvers
      user_solution (list of str): 
         user-specified list of copy number configurations.
   Returns (CNSolution):
      CNSolution describing the user-provided or optimal ILP solution
   """
   if user_solution is not None:
      return [_parse_user_solution(gene, user_solution)]
   else:
      _print_coverage(gene, sam)

      # TODO: filter CN configs with non-resent alleles
      # Calculate max. possible CN of the gene
      max_observed_cn = 1 + max(
         int(round(sam.coverage.region_coverage(g, r))) 
         for g in gene.regions 
         for r in gene.regions[g])
      log.debug('Maximum CN = {}', max_observed_cn)

      region_cov = _region_coverage(gene, sam)
      configs = _filter_configs(gene, sam)
      sol = solve_cn_model(gene, configs, max_observed_cn, region_cov, solver)

      return sol


def solve_cn_model(gene: Gene, cn_configs: Dict[str, CNConfig], 
                   max_cn: int, region_coverage: Dict[GeneRegion, Tuple[float, float]], 
                   solver: str) -> List[CNSolution]:
   """
   Solve copy number ILP model (a.k.a. closest vector problem).
   Params:
      cn_configs (dict of str: gene.CNConfig):
         dictionary of copy number configurations (vectors) to consider in the model
      max_cn (int):
         maximum copy number of the sample
      region_coverage (dict of gene.GeneRegion: (main_gene_cn, pseudogene_cn)):
         dictionary that provides the copy number of the main gene and the pseudogene 
         for each region
      solver:
         ILP solver to use. Check lpinterface.py for available solvers
   Returns (list of CNSolution):
      CNSolutions describing the optimal solution
   """

   # Model parameters
   LEFT_FUSION_PENALTY = 0.1
   PCE_PENALTY_COEFF = 1.5
   MAX_CN_ERROR = 10
   PARSIMONY_PENALTY = 0.5

   log.debug('Detecting CN among: {}', ', '.join(sorted(cn_configs)))

   # Initialize the LP model
   model = lpinterface.model('aldy_cnv', solver)

   # List of CN configurations (a.k.a. structures)
   # dict of (name, number): structure, where multiple copies of the same name get different numbers
   # (because of binary LP restrictions).
   # Note that number = {0, -1} represents *full configuration* with *all* pseudogenes. 
   # Thus a diploid genome must have *2* full configurations.
   # Any number > 0 describes only the main gene configuration (a.k.a. "weak" configurations), and there
   # can be multiple of such configurations.
   structures = {(name, 0): structure for name, structure in cn_configs.items()}
   for a, ai in list(structures.keys()):
      # Add another complete haplotype (assuming diploid genomes)   
      structures[(a, -1)] = structures[(a, 0)] 
      if cn_configs[a].kind in [CNConfig.CNConfigType.DELETION, CNConfig.CNConfigType.LEFT_FUSION]:
         continue
      for i in range(1, max_cn):
         structures[(a, i)] = copy.deepcopy(structures[(a, 0)])
         for g in structures[(a, i)].cn:
            # if it is pseudog, remove one copy (i.e. create "weak configuration")
            if g != 0:
               structures[(a, i)].cn[g] = {r: v - 1 for r, v in structures[(a, i)].cn[g].items()}

   # Add one binary variable to model for each structure copy.
   # Uppercase variables are LP variables
   A = {(a, ai): model.addVar(vtype='B', name='A_{}_{}'.format(a, ai)) for a, ai in structures}

   # We assume diploid genome, so the number of haplotype-inducing configurations is at most 2
   haplo_inducing = model.quicksum(A[a] for a in A if a[1] <= 0)
   model.addConstr(haplo_inducing == 2)
   log.trace('LP constraint: {} == 2', haplo_inducing)

   # Ensure that binary LP is properly formed (i.e. A_i <= A_{i-1})
   for a, ai in structures:
      if ai == -1:
         log.trace("LP constraint: A_-1 <= A_0 for {}", a)
         model.addConstr(A[(a, ai)] <= A[(a, 0)]) # second haplotype is present only if the first one is there
      elif ai > 0:
         log.trace('LP constraint: A_{} <= A_{} for {}', ai, ai - 1, a)
         model.addConstr(A[(a, ai)] <= A[(a, ai - 1)])
      
   # Form the error variables
   E = {}
   for r, (exp_cov0, exp_cov1) in region_coverage.items():
      expr = 0
      for s, structure in structures.items():
         if r in structure.cn[0]:
            expr += A[s] * structure.cn[0][r]
         if r in structure.cn[1]:
            expr -= A[s] * structure.cn[1][r]
      E[r] = model.addVar(name='E_{}{}'.format(*r), lb=-MAX_CN_ERROR, ub=MAX_CN_ERROR)

      log.trace('LP contraint: {} == E_{} + {}', exp_cov0 - exp_cov1, r, expr)
      model.addConstr(expr + E[r] == exp_cov0 - exp_cov1)

   # Set objective: minimize absolute errors AND the number of alleles (max. parsimony)
   # PCE_REGION (in CYP2D6) is penalized with extra score
   objective = model.abssum(E.values(), coeffs={PCE_REGION: PCE_PENALTY_COEFF}) 
   # Minimize the number of alleles among equal solutions
   objective += PARSIMONY_PENALTY * sum(A.values())
   # Penalize left fusions (further ensure max. parsimony)
   fusion_cost = model.quicksum(A[s, k] for s, k in A if cn_configs[s].kind == CNConfig.CNConfigType.LEFT_FUSION)
   objective += LEFT_FUSION_PENALTY * fusion_cost
   log.trace('LP objective: {}', objective)

   # Solve the model 
   try:
      status, opt, solutions = model.solveAll(objective, A)
      log.debug('LP status: {}, opt: {}', status, opt)
   except lpinterface.NoSolutionsError:
      return CNSolution(score=float('inf'), solution=[], region_cn={}, gene=gene)
   
   # Get final CN vector (i.e. total integer CN for each region)
   result = []
   for sol in solutions:
      log.debug('Solution: {}', ', '.join('*' + str(s) for s, _ in sol))

      vec = collections.defaultdict(lambda: collections.defaultdict(int))
      for conf in sol:
         for g in structures[conf].cn:
            for r in structures[conf].cn[g]:
               vec[g][r] += structures[conf].cn[g][r]
      result.append(CNSolution(
         score=opt, 
         solution=collections.Counter(s for s, _ in sol), 
         region_cn={a: dict(b) for a, b in vec.items()}, 
         gene=gene))

   return result


def _filter_configs(gene: Gene, sam: Sample) -> Dict[str, CNConfig]:
   """
   Filters out all low-quality mutations and CN configurations not supported 
   by high-quality mutations.
   Returns:
      a dictionary describing feasible CN configurationsants
   """

   cov = sam.coverage.filtered(lambda mut, cov, total, thres: \
      Coverage.basic_filter(mut, cov, total, thres / MAX_CN))
   configs = copy.deepcopy(gene.cn_configs)
   for an in sorted(gene.cn_configs):
      if an not in gene.alleles:
         continue # this is just a CN description w/o any mutations
      if any(cov[m] <= 0 for m in gene.alleles[an].func_muts):
         s = ('{} in {}'.format(m, gene.region_at(m.pos))
            for m in gene.alleles[an].func_muts
            if cov[m] <= 0)
         log.trace('Removing {} because of {}', an, ' and '.join(s))
         del configs[an]
   return configs


def _region_coverage(gene: Gene, sam: Sample) -> Dict[GeneRegion, Tuple[float, float]]:
   """
   Calculate the coverage of the main gene and pseudogene for each region
   Returns dict of GeneRegion: (float, float), where the key is the region (e.g. (1, EXON))
   and the value is the coverage of the main gene (0) and the pseudogene (1)
   """
   
   if 1 in gene.regions: # do we have pseudogenes at all?
      cov = {r: (sam.coverage.region_coverage(0, r), sam.coverage.region_coverage(1, r)) 
             for r in gene.unique_regions if r != PCE_REGION}
      # HACK: by default, CYP2D6 does not have PCE region, so insert dummy region to allow easy calculation below
      if PCE_REGION in gene.regions[1] and PCE_REGION not in gene.regions[0]:
         cov[PCE_REGION] = (0, sam.coverage.region_coverage(1, PCE_REGION))
      return cov
   else:
      return {r: (sam.coverage.region_coverage(0, r), 0) for r in gene.unique_regions}


def _print_coverage(gene: Gene, sam: Sample) -> None:
   """Pretty-prints region coverage vectors"""
   regions = set(r for g in gene.regions for r in gene.regions[g])
   for r in sorted(regions):
      log.debug(
         'Region {:>5} {:2}: {:5.2f} {:5.2f} {}', 
         r.kind, r.number,
         sam.coverage.region_coverage(0, r) if r in gene.regions[0] else .0,
         sam.coverage.region_coverage(1, r) if r in gene.regions[1] else .0,
         '* with diff = {:5.2f}'.format(
            (sam.coverage.region_coverage(0, r) if r in gene.regions[0] else .0) - 
            (sam.coverage.region_coverage(1, r) if r in gene.regions[1] else .0))
         if r in gene.unique_regions else '')
      

def _parse_user_solution(gene: Gene, sols: List[str]) -> CNSolution: 
   """
   Parses the list of user-provided solutions
   Params:
      gene (gene.Gene): a gene instance
      sols (list of str): list of CN configurations 
   """
   result, vec = [], collections.defaultdict(int)
   sols = collections.Counter(sols)
   for sol, sol_cnt in sols.items():
      if sol not in gene.cn_configs:
         raise AldyException(
            'Given copy number solution contains unknown copy number configuration {}. '.format(sol) + 
            'Please run aldy --show-cn for the list the valid configurations')
      for i in range(sol_cnt):
         result.append((sol, i))
         log.debug('Solution (user-provided): {}', result[-1])
         for regions in gene.cn_configs[sol].values():
            for r, v in regions.items():
               vec[r] += v
   return CNSolution(score=0, solution=result, region_cn=dict(vec), gene=gene)





