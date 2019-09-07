# 786

# Aldy source: solutions.py
#   This file is subject to the terms and conditions defined in
#   file 'LICENSE', which is part of this source code package.


from typing import Dict, List, Tuple, Optional

import collections

from .common import *
from .gene import Gene, GeneRegion, Mutation


class CNSolution(collections.namedtuple('CNSolution', ['score', 'solution', 'gene', 'region_cn'])):
   """
   Describes a potential (possibly optimal) copy-number configuration.
   Immutable class.

   Attributes:
      score (float):
         ILP model error score (0 for user-provided solutions).
      solution (dict[str, int]):
         Dictionary of copy-number configurations where a value denotes the copy-number
         of each configuration (e.g. ``{1: 2}`` means that there are two copies of \*1
         configuration).
      region_cn (dict[:obj:`aldy.common.GeneRegion`, int]):
         Dictionary of region copy numbers in this solution.
      gene (:obj:`aldy.gene.Gene`):
         Gene instance.

   Notes:
      Has custom printer (``__str__``).
   """

   def __new__(self, score: float, solution: List[str], gene: Gene):
      vec: Dict[int, Dict[GeneRegion, float]] = collections.defaultdict(lambda: collections.defaultdict(int))
      for conf in solution:
         for g in gene.cn_configs[conf].cn:
            for r in gene.cn_configs[conf].cn[g]:
               vec[g][r] += gene.cn_configs[conf].cn[g][r]
      return super(CNSolution, self).__new__(self,
                                             score,
                                             collections.Counter(solution),
                                             gene,
                                             {a: dict(b) for a, b in vec.items()})


   def position_cn(self, pos: int) -> float:
      """
      Returns:
         float: Copy number of the loci ``pos``.
      """
      try:
         g, region = self.gene.region_at(pos)
         return self.region_cn[g][region]
      except KeyError:
         return 0


   def _solution_nice(self):
      return ','.join(f'{v}x*{k}'
                      for k, v in sorted(self.solution.items(),
                                         key=lambda x: allele_sort_key(x[0])))


   def __str__(self):
      regions = sorted(set(r for g in self.region_cn for r in self.region_cn[g]))
      return 'CNSol[{:.2f}; sol=({}); cn={}]'.format(
         self.score,
         self._solution_nice(),
         '|'.join(''.join('{:.0f}'.format(self.region_cn[g][r])
                          if r in self.region_cn[g] else '_'
                          for r in regions)
                  for g in sorted(self.region_cn)))


class SolvedAllele(collections.namedtuple('SolvedAllele', ['major', 'minor', 'added', 'missing'])):
   """
   Describes a candidate star-allele configuration.
   Immutable class.

   Attributes:
      major (str):
         Major star-allele identifier.
      minor (str, optional):
         Minor star-allele identifier. Can be None.
      added (tuple[:obj:`aldy.gene.Mutation`]):
         Tuple of mutations that are added to this copy of a major/minor star-allele
         (e.g. these mutations are not present in the database defition of allele).
      missing (tuple[:obj:`aldy.gene.Mutation`]):
         Tuple of mutations that are ommited from this copy of a major/minor star-allele
         (e.g. these mutations are present in the database defition of allele but not in the sample).

   Notes:
      Has custom printer (``__str__``).
   """


   def major_repr(self):
      return '*{}{}'.format(self.major,
         ''.join(' +' + str(m) for m in sorted(m for m in self.added if m.is_functional)))


   def __str__(self):
      return '*{}{}{}'.format(
         self.minor if self.minor else self.major,
         ''.join(' +' + str(m) for m in sorted(self.added,
                                               key=lambda m: (-m.is_functional, m.pos, m.op))),
         ''.join(' -' + str(m) for m in sorted(self.missing)))


class MajorSolution(collections.namedtuple('MajorSolution', ['score', 'solution', 'cn_solution'])):
   """
   Describes a potential (possibly optimal) major star-allele configuration.
   Immutable class.

   Attributes:
      score (float):
         ILP model error score (0 for user-provided solutions).
      solution (dict[:obj:`SolvedAllele`, int]):
         Dictionary of major star-alleles where each major star-allele is
         associated with its copy number
         (e.g. ``{1: 2}`` means that we have two copies of \*1).
      cn_solution (:obj:`aldy.solutions.CNSolution`):
         Associated copy-number solution used for calculating the major
         star-alleles.

   Notes:
      Has custom printer (``__str__``).
   """


   def _solution_nice(self):
      return ', '.join(f'{v}x{s}'
                       for s, v in sorted(self.solution.items(),
                                          key=lambda x: allele_sort_key(x[0].major)))


   def __str__(self):
      return f'MajorSol[{self.score:.2f}; ' + \
             f'sol=({self._solution_nice()}); ' + \
             f'cn={self.cn_solution}'


class MinorSolution(collections.namedtuple('MinorSolution', ['score', 'solution', 'major_solution'])):
   """
   Describes a potential (possibly optimal) minor star-allele configuration.
   Immutable class.

   Attributes:
      score (float):
         ILP model error score (0 for user-provided solutions).
      solution (list[:obj:`SolvedAllele`]):
         List of minor star-alleles in the solution.
         Modifications to the minor alleles are represented in :obj:`SolvedAllele` format.
      major_solution (:obj:`aldy.solutions.MajorSolution`):
         Major star-allele solution used for calculating the minor star-allele assignment.
      diplotype (str):
         Assigned diplotype string (e.g. ``*1/*2``).

   Notes:
      Has custom printer (``__str__``).
   """
   diplotype = ''


   def _solution_nice(self):
      return ', '.join(str(s)
                       for s in sorted(self.solution,
                                       key=lambda x: allele_sort_key(x.minor)))


   def __str__(self):
      return f'MinorSol[{self.score:.2f}; ' + \
             f'sol=({self._solution_nice()}); ' + \
             f'major={self.major_solution}'
