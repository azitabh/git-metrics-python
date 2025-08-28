# git-metrics-python
Scripts to get contribution metrics for set of users 



## Commands to run

#### this is to get a report of total contributions only. something you see as green dots in the public profile.. this doesn't need admin access of org.
```
python3 git_metrics.py <access-code> 2025-04-02 2025-08-01 <source-file-path-with-list-of-users> <destination-file-path>
```
#### output file format
```
NAme,Username,Email,Contribution
Abc Xyz,handle,dummy@org.co,232
```

#### this is to get a more detailed report, listing commits, PRs, reviewes etc. this needs admin access(or just a access higher than member - exact access has to be figured out)
```
python3 git_metrics_detailed.py <access-code> 2025-04-02 2025-08-01 <source-file-path-with-list-of-users> <destination-file-path>
```
#### Output file format
```
Name,GitHandle,Email,TotalContributions,CommitContributions,IssueContributions,PullRequestContributions,PullRequestReviewContributions,RepositoryContributions,RestrictedContributions
Abc Xyz,handle,dummy@org.co,232,101,0,83,48,0,0
```

## Step to generate input file
Go to People section in the org's github page and use export option
